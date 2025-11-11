from functools import wraps

from django.http import HttpResponseForbidden

from apps.policy.engine import can


def require_perm(resource_key: str, action_key: str, *, org_key: str = "", extra=None):
    def deco(f):
        @wraps(f)
        def wrapper(request, *args, **kwargs):
            obj = kwargs.get("obj", None)
            if not can(request.user, action_key, resource_key, obj=obj, org_key=org_key, extra=extra):
                return HttpResponseForbidden("Permission denied")
            return f(request, *args, **kwargs)

        return wrapper

    return deco
