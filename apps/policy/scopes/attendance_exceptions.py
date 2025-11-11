from __future__ import annotations

from typing import Set

from django.db import models
from django.db.models import Q, QuerySet

from apps.policy.models import Policy, Resource, Action, RoleAssignment
from apps.policy.scopes.base import ScopeStrategy, ScopeResult
from apps.policy.scopes.registry import register
from .user_directory import descendant_ids


@register("attendance.exceptions", "list")
class AttendanceExceptionListScope(ScopeStrategy):
    """
    Scopes list visibility for AttendanceException.

    Interprets Policy.ConditionKind for this resource/action:
      - NONE                 => global_access
      - OWN_OBJECT           => own_self      (obj.user_id == user.id)
      - OWN_AUTHOR           => own_author    (obj.decided_by_id == user.id)
      - OWN_CURATOR          => own_curator   (obj.hr_user_id == user.id)
      - OWN_DEPT             => self_subdept_only (user's own department/top-dept)
      - ASSIGNMENT_SCOPE     => dept_ids via RoleAssignment.org_key (and its descendants)
      - SPECIFIC_DEPTS       => dept_ids from policy.param_departments
    """

    def resolve(self, user) -> ScopeResult:
        res = ScopeResult()
        if not getattr(user, "is_authenticated", False):
            return res
        if getattr(user, "is_superuser", False):
            res.global_access = True
            return res

        # Resolve ids for (resource, action)
        try:
            res_id = Resource.objects.only("id").get(key="attendance.exceptions").id
            act_id = Action.objects.only("id").get(key="list").id
        except (Resource.DoesNotExist, Action.DoesNotExist):
            return res

        # Collect role assignments (direct or via groups), enabled and valid (if you add validity filters later)
        ras = RoleAssignment.objects.filter(enabled=True).filter(
            models.Q(user=user) | models.Q(group__in=user.groups.all())
        ).only("role_id", "org_key")

        role_ids = {ra.role_id for ra in ras}
        if not role_ids:
            # No explicit roles — usually allow own items by default (optional)
            res.own_self = True
            return res

        # Policies for this resource+action
        pols = Policy.objects.filter(
            enabled=True,
            role_id__in=role_ids,
            resource_id=res_id,
            action_id=act_id,
        ).only(
            "condition_kind", "param_departments", "org_key"
        ).order_by("-priority", "id")

        # Expand dept scope from assignments with org_key if any policy uses ASSIGNMENT_SCOPE
        # We compute once; it's cheap even if unused.
        ra_scoped_depts: Set[int] = set()
        for ra in ras:
            if ra.org_key:
                try:
                    ra_scoped_depts |= descendant_ids(int(ra.org_key))
                except ValueError:
                    pass  # ignore non-int org_keys

        # Fold policies in priority order (you already do priority per-policy elsewhere;
        # for scoping we OR the slices).
        for p in pols:
            ck = p.condition_kind

            if ck == Policy.ConditionKind.NONE:
                res.global_access = True
                # global trumps everything else
                return res

            if ck == Policy.ConditionKind.OWN_OBJECT:
                res.own_self = True

            if ck == Policy.ConditionKind.OWN_AUTHOR:
                res.own_author = True

            if ck == Policy.ConditionKind.OWN_CURATOR:
                res.own_curator = True

            if ck == Policy.ConditionKind.OWN_DEPT:
                res.self_subdept_only = True

            if ck == Policy.ConditionKind.ASSIGNMENT_SCOPE:
                res.dept_ids |= ra_scoped_depts

            if ck == Policy.ConditionKind.SPECIFIC_DEPTS and p.param_departments:
                # if you want descendants for specific_depts too, map with descendant_ids here
                res.dept_ids |= {int(x) for x in p.param_departments if x is not None}

        return res

    def filter_queryset(self, qs: QuerySet, user) -> QuerySet:
        res = self.resolve(user)
        if getattr(user, "is_superuser", False) or res.global_access:
            return qs

        flt = Q()

        # Ownership slices
        if res.own_self:
            flt |= Q(employee_id=user.id)
        if res.own_author:
            flt |= Q(decided_by_id=user.id)
        if res.own_curator:
            flt |= Q(hr_user_id=user.id)

        # Department scopes
        # Choose the field representing the exception's department.
        # Most often attendance exception belongs to the employee's department:
        if res.dept_ids:
            flt |= Q(user__top_level_department_id__in=list(res.dept_ids)) | Q(
                user__department_id__in=list(res.dept_ids))
        if res.self_subdept_only and getattr(user, "top_level_department_id", None) is not None:
            flt |= Q(user__top_level_department_id=user.top_level_department_id) | Q(
                user__department_id=user.department_id)

        return qs.none() if flt == Q() else qs.filter(flt).distinct()
