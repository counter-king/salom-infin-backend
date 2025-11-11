from rest_framework.permissions import BasePermission

from apps.policy.engine import can


class HasDynamicPermission(BasePermission):
    def has_permission(self, request, view):
        rk = getattr(view, "resource_key", None)
        if not rk:
            return True
        ak = getattr(view, "action_key_map", {}).get(getattr(view, "action", None)) or getattr(view, "action_key", None)
        if not ak:
            return True
        obj = getattr(view, "get_permission_object", lambda: None)()
        return can(request.user, ak, rk, obj=obj)

    def has_object_permission(self, request, view, obj):
        rk = getattr(view, "resource_key", None)
        ak = getattr(view, "action_key_map", {}).get(getattr(view, "action", None)) or getattr(view, "action_key", None)
        if not rk or not ak:
            return True
        return can(request.user, ak, rk, obj=obj)
