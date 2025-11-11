from django.db.models import Model
from threading import local, current_thread

_thread_locals = local()


class GlobalUserMiddleware(object):
    """
    Sets the current authenticated user in threading locals

    Usage example:
        from app_name.middleware import get_current_user
        user = get_current_user()
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        setattr(_thread_locals, 'user_{0}'.format(current_thread().name), request.user)
        setattr(_thread_locals, 'device_{0}'.format(current_thread().name), get_device_type(request))

        response = self.get_response(request)
        key = 'user_{0}'.format(current_thread().name)

        if hasattr(_thread_locals, key):
            delattr(_thread_locals, key)
        return response


def get_current_user():
    return getattr(_thread_locals, 'user_{0}'.format(current_thread().name), None)


def get_signed_in_user():
    return get_current_user().id if isinstance(get_current_user().id, Model) else None


def get_current_user_id():
    user = get_current_user()
    return user.id if user else None


def get_current_company_id():
    return getattr(_thread_locals, 'company_id_{0}'.format(current_thread().name), None)


def set_current_company_id(company_id):
    setattr(_thread_locals, 'company_id_{0}'.format(current_thread().name), company_id)


def is_business_mobile():
    # print(getattr(_thread_locals, 'device_{0}'.format(current_thread().name), "w"))
    return getattr(_thread_locals, 'device_{0}'.format(current_thread().name), "w") in (
        'a-business',
        'i-business',
        'android-business',
        'ios-business',
        'android_b'
    )


def is_client_mobile():
    return getattr(_thread_locals, 'device_{0}'.format(current_thread().name), "w") in (
        'a-client',
        'i-client',
        'android-client',
        'ios-client',
        'android_c'
    )


def is_mobile():
    return is_business_mobile() or is_client_mobile()


def get_device_type(request):
    # print('im here!')
    result = request.META.get('HTTP_DEVICE_TYPE') or \
             request.META.get('DEVICE_TYPE') or \
             request.COOKIES.get("HTTP_DEVICE_TYPE") or \
             request.COOKIES.get("DEVICE_TYPE")
    # print("\n\n\n", result ,"\n\n\n")
    return result
