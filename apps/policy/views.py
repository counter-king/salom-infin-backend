from __future__ import annotations

from django.db.models import OuterRef, Subquery, Exists, Q
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.policy.engine import can
from apps.policy.logic import _valid_window_q, _org_match_q, user_role_ids, my_policies, my_resources
from apps.policy.models import Resource, Action, Role, Policy, RoleAssignment
# from apps.policy.permissions import IsSuperuserOrStaff
from apps.policy.serializers import (
    ResourceSerializer, ActionSerializer, RoleSerializer,
    PolicySerializer, RoleAssignmentSerializer
)
from apps.user.models import User


# --------- Read-only dictionaries ----------
class ResourceViewSet(mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    queryset = (Resource.objects.
                select_related("parent__parent").
                prefetch_related("children").
                filter(parent__isnull=True))
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated, ]


class ActionViewSet(mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    queryset = Action.objects.all().order_by("key")
    serializer_class = ActionSerializer
    permission_classes = [IsAuthenticated, ]


# --------- Role management ----------
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("name")
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, ]


# --------- Policy management ----------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.select_related("role", "resource", "action").all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated, ]
    filterset_fields = ("role", "resource", "action", "effect", "enabled", "condition_kind", "org_key")
    search_fields = ("role__name", "resource__key", "action__key", "org_key")
    ordering_fields = ("priority", "id", "created_date", "modified_date")
    ordering = ("-priority", "id")


# --------- Role assignments ----------
class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.select_related("role", "user", "group").all()
    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsAuthenticated, ]
    filterset_fields = ("role", "user", "group", "enabled", "org_key")
    search_fields = ("role__name", "user__username", "group__name", "org_key")
    ordering_fields = ("id", "created_at", "updated_at")
    ordering = ("-id",)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------- Utility endpoints ---------
@api_view(["POST"])
@permission_classes([IsAuthenticated, ])
def check_permission(request):
    """
    POST body:
      {
        "user_id": 123,
        "resource_key": "compose.document",
        "action_key": "view",
        "object": {"id": 10, "department_id": 42, ...}  # optional object dict
        "org_key": "42",         # optional scope
        "extra": {...}           # optional ctx
      }
    Returns: {"allowed": true/false}
    """

    user_id = request.data.get("user_id")
    resource_key = request.data.get("resource_key")
    action_key = request.data.get("action_key")
    obj = request.data.get("object") or None
    org_key = request.data.get("org_key") or ""
    extra = request.data.get("extra") or None

    if not user_id or not resource_key or not action_key:
        return Response({"message": "user_id, resource_key, action_key are required."},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        u = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    allowed = can(u, action_key, resource_key, obj=obj, org_key=org_key, extra=extra)
    return Response({"allowed": bool(allowed)})


# @api_view(["GET"])
# @permission_classes([IsAuthenticated, ])
# def compose_list_scope(request, user_id: int):
#     """
#     Inspect effective list scope for Compose (journals/types/subtypes/depts/ownership).
#     GET /api/acl/compose/scope/{user_id}/
#     """
#     from django.contrib.auth import get_user_model
#     User = get_user_model()
#     try:
#         u = User.objects.get(pk=user_id)
#     except User.DoesNotExist:
#         return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
#
#     scope = resolve_compose_list_scope(u)
#     # make sets JSON-friendly
#     scope["journal_ids"] = list(scope["journal_ids"])
#     scope["doc_type_ids"] = list(scope["doc_type_ids"])
#     scope["doc_sub_type_ids"] = list(scope["doc_sub_type_ids"])
#     scope["dept_ids"] = list(scope["dept_ids"])
#     return Response(scope, status=200)


def _top_policies_qs(request_user, *, org_key=None, at=None):
    """
    SQL-level priority resolution:
    - Start from candidate policies = my_policies(user, org_key)
    - Keep only the top policy per (resource, action) by (priority desc, id asc)
    """
    role_ids_sq = user_role_ids(request_user, org_key=org_key, at=at)

    # Universe of candidates (already filtered by enabled/valid/org & role membership)
    candidates = my_policies(request_user, org_key=org_key, at=at).values(
        "id", "resource_id", "action_id", "priority"
    )

    # A higher (or same priority with lower id) policy exists for same (resource, action)?
    higher_exists = Policy.objects.filter(
        enabled=True,
        resource_id=OuterRef("resource_id"),
        action_id=OuterRef("action_id"),
        role_id__in=Subquery(role_ids_sq),
    ).filter(
        _valid_window_q("valid", at)
    ).filter(
        _org_match_q(org_key)
    ).filter(
        Q(priority__gt=OuterRef("priority")) |
        (Q(priority=OuterRef("priority")) & Q(id__lt=OuterRef("id")))
    )

    top = (
        Policy.objects.filter(id__in=Subquery(candidates.values("id")))
        .select_related("role", "resource", "action")
        .annotate(_higher=Exists(higher_exists))
        .filter(_higher=False)
        .order_by("resource__key", "action__key")  # nice stable ordering
    )
    return top


class MePoliciesViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET /me/policies?org_key=<org_key>&effect=allow|deny
    Returns the *effective* (top) policy per (resource, action).
    """
    serializer_class = PolicySerializer
    filterset_fields = ("org_key", "effect")

    def get_queryset(self):
        org_key = self.request.GET.get("org_key", None)
        only = self.request.GET.get("effect", "").lower()
        qs = _top_policies_qs(self.request.user, org_key=org_key)
        if only in ("allow", "deny"):
            qs = qs.filter(effect=only)
        return qs


class MeResourcesViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET /me/resources?org=<org_key>
    Lists resources with at least one ALLOW action (after priority resolution).
    Adds `allowed_actions` = list of action keys that are effectively ALLOW.
    """
    serializer_class = ResourceSerializer

    def list(self, request, *args, **kwargs):
        org_key = request.query_params.get("org_key", None)
        user = request.user

        # 1) Base resources user can access (ALLOW winners exist)
        resources_qs = my_resources(user, org_key=org_key)

        # 2) Build allowed actions map from effective top policies (ALLOW only)
        top = _top_policies_qs(user, org_key=org_key).filter(effect=Policy.EFFECT_ALLOW)

        # Use values_list to avoid select_related/only pitfalls
        allowed_map = {}  # resource_id -> set(action_key)
        for res_id, act_key in top.values_list("resource_id", "action__key"):
            allowed_map.setdefault(res_id, set()).add(act_key)

        # 3) Serialize with allowed_actions injected
        page = self.paginate_queryset(resources_qs)
        objs = page if page is not None else list(resources_qs)

        for r in objs:
            r.allowed_actions = sorted(allowed_map.get(r.id, set()))

        serializer = self.get_serializer(objs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
