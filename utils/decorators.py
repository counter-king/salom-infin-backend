from functools import wraps

from django.core.exceptions import PermissionDenied
from drf_yasg import openapi


def login_required(resolver_method):
    @wraps(resolver_method)
    def wrapped_resolver(cls, root, info, *args, **kwargs):
        user = info.context.user
        if not user.is_authenticated or not user.is_superuser:
            raise PermissionDenied("Superuser access required.")
        return resolver_method(cls, root, info, *args, **kwargs)

    return wrapped_resolver


def superuser_required(resolver_method):
    @wraps(resolver_method)
    def wrapped_resolver(cls, root, info, *args, **kwargs):
        user = info.context.user
        if not user.is_authenticated or not user.is_superuser:
            raise PermissionDenied("Superuser access required.")
        return resolver_method(cls, root, info, *args, **kwargs)

    return wrapped_resolver


def global_parameter(param_name, param_type, param_description):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            request._swagger_params = request._swagger_params or []
            request._swagger_params.append(openapi.Parameter(
                name=param_name,
                in_=param_type,
                type=param_type,
                description=param_description,
                required=False,
            ))
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
