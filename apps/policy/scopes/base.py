from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set

from django.db.models import QuerySet


@dataclass
class ScopeResult:
    global_access: bool = False
    dept_ids: Set[int | str] = field(default_factory=set)
    journal_ids: Set[int] = field(default_factory=set)
    doc_type_ids: Set[int] = field(default_factory=set)
    doc_sub_type_ids: Set[int] = field(default_factory=set)
    own_self: bool = False
    own_author: bool = False
    own_curator: bool = False
    self_subdept_only: bool = False

    def empty(self) -> bool:
        return (
                not self.global_access and
                not self.own_self and
                not self.dept_ids and
                not self.journal_ids and
                not self.doc_type_ids and
                not self.doc_sub_type_ids and
                not self.own_author and
                not self.own_curator and
                not self.self_subdept_only
        )


class ScopeStrategy:
    """
    A strategy resolves list visibility for (resource, action) and can prefilter a queryset.
    Implement resolve(user) and filter_queryset(qs, user).
    """
    resource_key: str
    action_key: str

    def resolve(self, user) -> ScopeResult:
        raise NotImplementedError

    def filter_queryset(self, qs: QuerySet, user) -> QuerySet:
        """
        Default: if no scope found, return none; if global, return qs.
        Subclasses should build Q() for their model fields.
        """
        res = self.resolve(user)
        if user.is_superuser or res.global_access:
            return qs
        if res.empty():
            return qs.none()
        return qs.none()
