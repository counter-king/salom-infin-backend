from __future__ import annotations
from typing import Set, Dict
from django.db import models
from django.db.models import Q, QuerySet
from apps.policy.models import Policy, Resource, Action, RoleAssignment
from apps.policy.scopes.base import ScopeStrategy, ScopeResult
from apps.policy.scopes.registry import register


@register("compose.document", "list")
class ComposeListScope(ScopeStrategy):
    def _resolve(self, user) -> ScopeResult:
        res = ScopeResult()
        if not getattr(user, "is_authenticated", False):
            return res
        if getattr(user, "is_superuser", False):
            res.global_access = True
            return res

        try:
            res_id = Resource.objects.only("id").get(key="compose.document").id
            act_id = Action.objects.only("id").get(key="list").id
        except (Resource.DoesNotExist, Action.DoesNotExist):
            return res

        ras = RoleAssignment.objects.filter(enabled=True).filter(
            models.Q(user=user) | models.Q(group__in=user.groups.all())
        ).only("role_id", "org_key")
        role_ids = {ra.role_id for ra in ras}
        if not role_ids:
            return res

        pols = Policy.objects.filter(
            enabled=True, effect=Policy.EFFECT_ALLOW,
            role_id__in=role_ids, resource_id=res_id, action_id=act_id
        ).only(
            "condition_kind",
            "param_journal_ids",
            "param_doc_type_ids",
            "param_doc_sub_type_ids",
            "org_key", "role_id"
        ).order_by("-priority", "id")

        role_scopes: Dict[int, Set[str]] = {}
        for ra in ras:
            role_scopes.setdefault(ra.role_id, set()).add(ra.org_key or "")

        user_dept = getattr(user, "department_id", None)

        for p in pols:
            k = p.condition_kind

            if k == Policy.ConditionKind.NONE:
                res.global_access = True
                return res

            if k == Policy.ConditionKind.SPECIFIC_JOURNALS:
                for x in (p.param_journal_ids or []):
                    res.journal_ids.add(int(x))

            elif k == Policy.ConditionKind.SPECIFIC_DOC_TYPES:
                for x in (p.param_doc_type_ids or []):
                    res.doc_type_ids.add(int(x))

            elif k == Policy.ConditionKind.SPECIFIC_DOC_SUBTYPES:
                for x in (p.param_doc_sub_type_ids or []):
                    res.doc_sub_type_ids.add(int(x))

            elif k == Policy.ConditionKind.ASSIGNMENT_SCOPE:
                assigned = role_scopes.get(p.role_id, set())
                if p.org_key:
                    if p.org_key in assigned:
                        res.dept_ids.add(p.org_key)
                else:
                    res.dept_ids.update(x for x in assigned if x)

            elif k == Policy.ConditionKind.OWN_DEPT:
                if user_dept is not None:
                    res.dept_ids.add(user_dept)

            elif k == Policy.ConditionKind.OWN_AUTHOR:
                res.own_author = True

            elif k == Policy.ConditionKind.OWN_CURATOR:
                res.own_curator = True

        return res

    def resolve(self, user) -> ScopeResult:
        return self._resolve(user)

    def filter_queryset(self, qs: QuerySet, user) -> QuerySet:
        res = self.resolve(user)
        if user.is_superuser or res.global_access:
            return qs

        flt = Q()
        if res.journal_ids:
            flt |= Q(journal_id__in=list(res.journal_ids))
        if res.doc_type_ids:
            flt |= Q(document_type_id__in=list(res.doc_type_ids))
        if res.doc_sub_type_ids:
            flt |= Q(document_sub_type_id__in=list(res.doc_sub_type_ids))
        if res.dept_ids:
            flt |= Q(sender_id__in=list(res.dept_ids))
        personal = Q()
        if res.own_author:
            personal |= Q(author_id=user.id)
        if res.own_curator:
            personal |= Q(curator_id=user.id)
        flt |= personal

        return qs.none() if flt == Q() else qs.filter(flt).distinct()
