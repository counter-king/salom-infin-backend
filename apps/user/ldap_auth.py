import os, ldap

from apps.user.models import User
from utils.exception import get_response_message, ValidationError2


def authenticate(username, password, request):
    LDAP_HOST = os.getenv('LDAP_HOST')
    conn = ldap.initialize(LDAP_HOST)

    try:
        result = conn.simple_bind_s(username, password)
    except ldap.INVALID_CREDENTIALS:
        message = get_response_message(request, 701)
        raise ValidationError2(message)
    except (ldap.SERVER_DOWN, ldap.LDAPError):
        message = get_response_message(request, 777)
        raise ValidationError2(message)
    finally:
        conn.unbind_s()

    user = User.objects.filter(ldap_login=username.split('@')[0]).first()

    if user:
        return user
    return None
