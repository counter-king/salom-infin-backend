from __future__ import annotations

import operator
from typing import Any, Dict, Optional, Iterable

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.utils import timezone

from apps.policy.models import Resource, Action, Role, Policy, RoleAssignment

_CACHE_KEY = "ac:compiled:v1"
_CACHE_TTL = 300  # seconds


def _compile_policies() -> Dict[str, Any]:
    res_keys = {r.id: r.key for r in Resource.objects.all()}
    act_keys = {a.id: a.key for a in Action.objects.all()}

    pol_index: Dict[int, Dict[tuple, list]] = {}
    now = timezone.now()
    for p in Policy.objects.filter(enabled=True).order_by("-priority", "id"):
        rk = res_keys.get(p.resource_id)
        ak = act_keys.get(p.action_id)

        if not rk or not ak:
            continue
        if p.valid_from and p.valid_from > now:
            continue
        if p.valid_until and p.valid_until <= now:
            continue

        by_res_act = pol_index.setdefault(p.role_id, {})
        by_res_act.setdefault((rk, ak), []).append({
            "effect": p.effect,
            "cond": p.condition or {},
            "org_key": p.org_key or "",
            "priority": p.priority,
        })

    user_roles: Dict[int, list] = {}
    group_roles: Dict[int, list] = {}
    for ra in RoleAssignment.objects.filter(enabled=True):
        entry = {"role_id": ra.role_id, "org_key": (ra.org_key or "")}

        if ra.valid_from and ra.valid_from > now:
            continue
        if ra.valid_until and ra.valid_until <= now:
            continue

        if ra.user_id:
            user_roles.setdefault(ra.user_id, []).append(entry)
        if ra.group_id:
            group_roles.setdefault(ra.group_id, []).append(entry)

    return {"pol_index": pol_index, "user_roles": user_roles, "group_roles": group_roles}


def _compiled() -> Dict[str, Any]:
    data = cache.get(_CACHE_KEY)
    if data is None:
        data = _compile_policies()
        cache.set(_CACHE_KEY, data, _CACHE_TTL)
    return data


def _jsonlogic(expr: Any, ctx: Dict[str, Any]) -> bool:
    if expr in (None, {}, []):
        return True
    if isinstance(expr, bool):
        return expr
    if isinstance(expr, (int, float, str)):
        return bool(expr)
    if not isinstance(expr, dict):
        return False

    def vget(path: str):
        parts = str(path).split(".")
        cur: Any = ctx
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        return cur

    for op, val in expr.items():
        if op == "var":
            return vget(val)
        if op == "and":
            return all(_jsonlogic(x, ctx) for x in val)
        if op == "or":
            return any(_jsonlogic(x, ctx) for x in val)
        if op == "!":
            return not _jsonlogic(val, ctx)
        if op in ("==", "!=", ">", ">=", "<", "<="):
            a, b = val
            a = _jsonlogic(a, ctx) if isinstance(a, dict) else a
            b = _jsonlogic(b, ctx) if isinstance(b, dict) else b
            ops = {
                "==": operator.eq, "!=": operator.ne,
                ">": operator.gt, ">=": operator.ge,
                "<": operator.lt, "<=": operator.le,
            }
            return ops[op](a, b)
        if op == "in":
            needle, hay = val
            needle = _jsonlogic(needle, ctx) if isinstance(needle, dict) else needle
            hay = _jsonlogic(hay, ctx) if isinstance(hay, dict) else hay
            try:
                return needle in hay
            except Exception:
                return False
        if op == "+":
            a, b = val
            aa = _jsonlogic(a, ctx) if isinstance(a, dict) else a
            bb = _jsonlogic(b, ctx) if isinstance(b, dict) else b
            try:
                return (aa or 0) + (bb or 0)
            except Exception:
                return 0
        if op == "*":
            a, b = val
            aa = _jsonlogic(a, ctx) if isinstance(a, dict) else a
            bb = _jsonlogic(b, ctx) if isinstance(b, dict) else b
            try:
                return (aa or 0) * (bb or 0)
            except Exception:
                return 0
    return False


def can(user, action_key: str, resource_key: str, obj: Optional[Any] = None,
        *, org_key: str = "", extra: Optional[Dict[str, Any]] = None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    compiled = _compiled()
    idx = compiled["pol_index"]
    granted = list(compiled["user_roles"].get(user.id, []))
    for g in user.groups.all().only("id"):
        granted.extend(compiled["group_roles"].get(g.id, []))
    if not granted:
        return False

    now = timezone.localtime()
    if obj is None:
        obj_map = {}
    elif isinstance(obj, dict):
        obj_map = obj
    else:
        obj_map = {}
        for f in dir(obj):
            if f.startswith("_"):
                continue
            try:
                obj_map[f] = getattr(obj, f)
            except Exception:
                pass

    ctx: Dict[str, Any] = {
        "user": {
            "id": user.id,
            "username": getattr(user, "username", None),
            "department_id": getattr(user, "department_id", None),
            "is_staff": getattr(user, "is_staff", False),
            "is_active": getattr(user, "is_active", True),
        },
        "obj": obj_map,
        "now": {"hour": now.hour, "minute": now.minute, "iso": now.isoformat()},
        "ctx": {"org_key": org_key},
    }
    if extra:
        ctx["ctx"].update(extra)

    decision = None
    for grant in granted:
        r_id = grant["role_id"]
        scope = grant.get("org_key", "")
        pols: Iterable[dict] = idx.get(r_id, {}).get((resource_key, action_key), [])
        for p in pols:
            pol_scope = p.get("org_key", "")
            if pol_scope and scope and pol_scope != scope:
                continue
            if not _jsonlogic(p.get("cond", {}), ctx):
                continue
            if p.get("effect") == "deny":
                return False
            decision = "allow"

    return decision == "allow"


def _bust_cache(*_args, **_kwargs):
    cache.delete(_CACHE_KEY)


for mdl in (Policy, RoleAssignment, Role, Resource, Action):
    post_save.connect(_bust_cache, sender=mdl)
    post_delete.connect(_bust_cache, sender=mdl)
