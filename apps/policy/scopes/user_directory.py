from __future__ import annotations

from typing import Set

from django.db import models
from django.db.models import Q, QuerySet

from apps.policy.models import Policy, Resource, Action, RoleAssignment
from apps.policy.scopes.base import ScopeStrategy, ScopeResult
from apps.policy.scopes.registry import register


# Choose your descendant resolver (MPTT or recursive CTE)
def descendant_ids(root_id: int) -> Set[int]:
    # Example with adjacency list + recursive CTE
    from django.db import connection
    ids: Set[int] = set()
    with connection.cursor() as cur:
        cur.execute("""
                    WITH RECURSIVE t AS (SELECT id
                                         FROM company_department
                                         WHERE id = %s
                                         UNION ALL
                                         SELECT d.id
                                         FROM company_department d
                                                  JOIN t ON d.parent_id = t.id)
                    SELECT id
                    FROM t;
                    """, [root_id])
        for (vid,) in cur.fetchall():
            ids.add(int(vid))
    return ids


@register("user.directory", "list")
class UserDirectoryListScope(ScopeStrategy):
    HEAD_NAMES = {"Department Head", "SubDept Head", "SubSubDept Head"}

    def resolve(self, user) -> ScopeResult:
        res = ScopeResult()
        if not getattr(user, "is_authenticated", False):
            return res
        if getattr(user, "is_superuser", False):
            res.global_access = True
            return res

        try:
            res_id = Resource.objects.only("id").get(key="user.directory").id
            act_id = Action.objects.only("id").get(key="list").id
        except (Resource.DoesNotExist, Action.DoesNotExist):
            return res

        ras = RoleAssignment.objects.filter(enabled=True).filter(
            models.Q(user=user) | models.Q(group__in=user.groups.all())
        ).select_related("role").only("role_id", "org_key", "role__name")

        role_ids = {ra.role_id for ra in ras}
        if not role_ids:
            # No explicit roles → limit to own sub-department
            res.self_subdept_only = True
            return res

        pols = Policy.objects.filter(
            enabled=True, effect=Policy.EFFECT_ALLOW,
            role_id__in=role_ids, resource_id=res_id, action_id=act_id
        ).only("condition_kind").order_by("-priority", "id")

        for ra in ras:
            if ra.role.name in self.HEAD_NAMES and ra.org_key:
                try:
                    root = int(ra.org_key)
                    res.dept_ids |= descendant_ids(root)
                except ValueError:
                    continue

        for p in pols:
            if p.condition_kind == Policy.ConditionKind.NONE:
                res.global_access = True
                return res
            if p.condition_kind == Policy.ConditionKind.OWN_DEPT:
                res.self_subdept_only = True

        return res

    def filter_queryset(self, qs: QuerySet, user) -> QuerySet:
        res = self.resolve(user)
        if user.is_superuser or res.global_access:
            return qs

        flt = Q()
        if res.dept_ids:
            flt |= Q(department_id__in=list(res.dept_ids))
        if res.self_subdept_only and getattr(user, "department_id", None) is not None:
            flt |= Q(department_id=user.department_id)

        return qs.none() if flt == Q() else qs.filter(flt).distinct()
