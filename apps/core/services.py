from django.db.models import Q
from django.utils import timezone

from apps.core.models import DepartmentManager, BranchManager


def _normalize(qs):
    """Compact sort_order to 0..n-1 (top = 0)."""
    ids = list(qs.order_by("sort_order", "id").values_list("id", flat=True))
    if not ids:
        return
    objs = {o.id: o for o in qs.filter(id__in=ids)}
    changed = False
    for new_so, pk in enumerate(ids):
        o = objs[pk]
        if o.sort_order != new_so:
            o.sort_order = new_so
            changed = True
    if changed:
        qs.model.objects.bulk_update(objs.values(), ["sort_order"])


def _swap_with_neighbor(scope_qs, obj, direction: str):
    """Swap obj with previous ('up') or next ('down') in ascending order."""
    scope = scope_qs.select_for_update().order_by("sort_order", "id")
    rows = list(scope)
    if not rows:
        return
    idx = next((i for i, r in enumerate(rows) if r.id == obj.id), None)
    if idx is None:
        return
    if direction == "up":
        if idx == 0:  # already top
            return
        a, b = rows[idx - 1], rows[idx]
    else:
        if idx == len(rows) - 1:  # already bottom
            return
        a, b = rows[idx], rows[idx + 1]
    a.sort_order, b.sort_order = b.sort_order, a.sort_order
    scope.model.objects.bulk_update([a, b], ["sort_order"])


def _move_to(scope_qs, obj, target_index: int):
    """
    Move `obj` to `target_index` (0-based, top=0) within `scope_qs`.
    Recomputes contiguous sort_order for the whole scope atomically.
    """
    scope = scope_qs.select_for_update().order_by("sort_order", "id")
    rows = list(scope)
    if not rows:
        return

    # clamp target
    n = len(rows)
    i = next((idx for idx, r in enumerate(rows) if r.id == obj.id), None)
    if i is None:
        return
    target = max(0, min(target_index, n - 1))
    if target == i:
        return

    # remove + insert
    row = rows.pop(i)
    rows.insert(target, row)

    # rewrite contiguous orders
    changed = False
    for new_so, r in enumerate(rows):
        if r.sort_order != new_so:
            r.sort_order = new_so
            changed = True
    if changed:
        scope.model.objects.bulk_update(rows, ["sort_order"])


def effective_department_managers(department_id, role=None):
    today = timezone.localdate()
    qs = DepartmentManager.objects.filter(
        department_id=department_id, is_active=True
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=today),
        Q(valid_until__isnull=True) | Q(valid_until__gte=today),
    )
    if role:
        qs = qs.filter(role=role)
    return qs.order_by("-is_primary", "sort_order")


def effective_branch_managers(branch_id):
    today = timezone.localdate()
    qs = BranchManager.objects.filter(
        branch_id=branch_id, is_active=True
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=today),
        Q(valid_until__isnull=True) | Q(valid_until__gte=today),
    )
    return qs.order_by("-is_primary", "sort_order")
