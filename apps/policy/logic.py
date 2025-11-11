from __future__ import annotations

from django.db.models import Q, Subquery, OuterRef, Exists
from django.utils import timezone

from .models import Policy, RoleAssignment, Resource


def _hhmm_to_minutes(hhmm: str) -> int:
    if not hhmm or ":" not in hhmm:
        return 0
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def compile_condition_json(policy) -> dict:
    kind = getattr(policy, "condition_kind", "none")

    if kind == "none":
        return {}

    if kind == "own_dept":
        return {"==": [{"var": "obj.department_id"}, {"var": "user.department_id"}]}

    if kind == "assignment_scope":
        return {"==": [{"var": "obj.department_id"}, {"var": "ctx.org_key"}]}

    if kind == "specific_depts":
        return {"in": [{"var": "obj.department_id"}, policy.param_departments]}

    if kind == "own_object":
        field = policy.param_owner_field or "user_id"
        return {"==": [{"var": f"obj.{field}"}, {"var": "user.id"}]}

    if kind == "own_author":
        return {"==": [{"var": "obj.author_id"}, {"var": "user.id"}]}

    if kind == "own_curator":
        return {"==": [{"var": "obj.curator_id"}, {"var": "user.id"}]}

    if kind == "specific_journals":
        return {"in": [{"var": "obj.journal_id"}, policy.param_journal_ids]}

    if kind == "specific_doc_types":
        return {"in": [{"var": "obj.document_type_id"}, policy.param_doc_type_ids]}

    if kind == "specific_doc_subtypes":
        return {"in": [{"var": "obj.document_sub_type_id"}, policy.param_doc_sub_type_ids]}

    if kind == "time_window":
        s = _hhmm_to_minutes(policy.param_time_start_hhmm or "00:00")
        e = _hhmm_to_minutes(policy.param_time_end_hhmm or "23:59")
        return {
            "and": [
                {">=": [{"+": [{"*": [{"var": "now.hour"}, 60]}, {"var": "now.minute"}]}, s]},
                {"<=": [{"+": [{"*": [{"var": "now.hour"}, 60]}, {"var": "now.minute"}]}, e]},
            ]
        }

    if kind == "advanced":
        return policy.param_advanced_ast or {}

    return {}


def _now(at=None):
    return at or timezone.now()


def _valid_window_q(prefix: str, at):
    """
    Build a validity filter for either RoleAssignment or Policy.
    prefix: 'valid' (for RoleAssignment) or 'valid' (both use same field names)
    """
    # Fields are valid_from/valid_until on both models
    f_from = f"{prefix}_from"
    f_until = f"{prefix}_until"
    now = _now(at)
    return (
            (Q(**{f"{f_from}__isnull": True}) | Q(**{f"{f_from}__lte": now})) &
            (Q(**{f"{f_until}__isnull": True}) | Q(**{f"{f_until}__gte": now}))
    )


def _org_match_q(org_key: str | None):
    """
    Policies/Assignments with blank org_key are considered global.
    If org_key is provided, accept rows where org_key is blank OR equals the provided key.
    """
    if not org_key:
        # Only global (blank) OR any org-specific? Choose global+any since user didn't scope.
        return Q(org_key__in=["", None]) | Q(org_key__gt="")  # accept all; tune if needed
    return Q(org_key__in=["", None]) | Q(org_key=org_key)


def user_role_ids(user, *, org_key: str | None = None, at=None):
    """
    Resolve roles granted to the user either directly or via group membership,
    filtered by enable flags, validity windows, and optional org scope.
    """
    groups = user.groups.all().values("id")
    ra_q = RoleAssignment.objects.filter(
        enabled=True
    ).filter(
        _valid_window_q("valid", at)
    ).filter(
        # Subject: direct or via group
        Q(user_id=user.id) | Q(group_id__in=Subquery(groups))
    ).filter(
        _org_match_q(org_key)
    ).values("role_id").distinct()

    return ra_q


def my_policies(user, *, org_key: str | None = None, at=None):
    """
    Return effective policies visible to the user (not yet resolved for conflicts).
    You can further fold these into allow/deny decisions per resource.action by priority.
    """
    role_ids_sq = user_role_ids(user, org_key=org_key, at=at)

    qs = (
        Policy.objects.select_related("role", "resource", "action")
        .filter(enabled=True)
        .filter(_valid_window_q("valid", at))
        .filter(Q(role_id__in=Subquery(role_ids_sq)))
        .filter(_org_match_q(org_key))
        .order_by("-priority", "id")  # highest priority first (matches Meta.ordering)
    )
    return qs


def my_resources(user, *, org_key: str | None = None, at=None):
    """
    All resources for which the user has at least one ALLOW policy for any action,
    after considering enabled/validity/org scope and policy priority/effect.
    This version resolves conflicts at the policy level per (resource, action)
    honoring priority: first match wins.
    """
    # Candidate policies
    pol_qs = my_policies(user, org_key=org_key, at=at).values("id", "resource_id", "action_id", "effect", "priority")

    # To honor priority per (resource, action), we keep only the top policy for that pair.
    # A common pattern is to use a NOT EXISTS anti-join for "no higher-priority policy exists".
    higher_exists = Policy.objects.filter(
        enabled=True,
        resource_id=OuterRef("resource_id"),
        action_id=OuterRef("action_id"),
        role_id__in=Subquery(user_role_ids(user, org_key=org_key, at=at)),
    ).filter(
        _valid_window_q("valid", at)
    ).filter(
        _org_match_q(org_key)
    ).filter(
        Q(priority__gt=OuterRef("priority")) | (Q(priority=OuterRef("priority")) & Q(id__lt=OuterRef("id")))
    )

    top_policies = (
        Policy.objects.filter(id__in=Subquery(pol_qs.values("id")))  # limit universe to candidate pols
        .annotate(_higher=Exists(higher_exists))
        .filter(_higher=False)  # keep only the top policy per (resource, action)
    )

    # Only ALLOW winners contribute resources
    allow_resource_ids = top_policies.filter(effect=Policy.EFFECT_ALLOW).values("resource_id")

    return (
        Resource.objects.filter(id__in=Subquery(allow_resource_ids))
        .order_by("key")
        .distinct()
    )


def my_permissions_matrix(user, *, org_key: str | None = None, at=None):
    """
    Compute a dict: {resource_key: {action_key: {"effect": "allow"/"deny", "policy_id": int}}}
    with priority/conflict resolution (first/top wins per resource.action).
    Useful for fast in-memory checks or to cache.
    """
    role_ids_sq = user_role_ids(user, org_key=org_key, at=at)
    base = (
        Policy.objects.select_related("resource", "action")
        .filter(enabled=True)
        .filter(_valid_window_q("valid", at))
        .filter(Q(role_id__in=Subquery(role_ids_sq)))
        .filter(_org_match_q(org_key))
        .order_by("resource_id", "action_id", "-priority", "id")  # group then top-first
        .values("id", "effect", "resource__key", "action__key", "priority")
    )

    matrix = {}
    seen = set()
    for row in base:
        key = (row["resource__key"], row["action__key"])
        if key in seen:
            continue  # already took the top policy
        seen.add(key)
        matrix.setdefault(row["resource__key"], {})[row["action__key"]] = {
            "effect": row["effect"],
            "policy_id": row["id"],
            "priority": row["priority"],
        }
    return matrix
