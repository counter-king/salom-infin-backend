import os

import ldap
from django.core.exceptions import ValidationError
from ldap.filter import escape_filter_chars

from apps.user.models import User
from utils.exception import get_response_message, ValidationError2


# def authenticate(username, password, request):
#     LDAP_HOST = os.getenv('LDAP_HOST')
#     conn = ldap.initialize(LDAP_HOST)
#
#     try:
#         result = conn.simple_bind_s(username, password)
#     except ldap.INVALID_CREDENTIALS:
#         message = get_response_message(request, 701)
#         raise ValidationError2(message)
#     except (ldap.SERVER_DOWN, ldap.LDAPError):
#         message = get_response_message(request, 777)
#         raise ValidationError2(message)
#     finally:
#         conn.unbind_s()
#
#     user = User.objects.filter(ldap_login=username.split('@')[0]).first()
#
#     if user:
#         return user
#     return None


def authenticate(username: str, password: str, request):
    LDAP_HOST = os.getenv("LDAP_HOST")  # e.g., "ldaps://ad.corp.example.com:636" or "ldap://..."
    BASE_DN = os.getenv("LDAP_BASE_DN", "OU=Bosh ofis,DC=cbu,DC=uz")  # e.g., "DC=corp,DC=example,DC=com"
    USE_STARTTLS = os.getenv("LDAP_STARTTLS", "0") == "1"

    if not LDAP_HOST or not BASE_DN:
        raise ValidationError("LDAP is not configured (LDAP_HOST / LDAP_BASE_DN missing).")

    conn = None
    try:
        # Connect
        conn = ldap.initialize(LDAP_HOST)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        conn.set_option(ldap.OPT_REFERRALS, 0)  # AD: avoid chasing referrals
        if LDAP_HOST.lower().startswith("ldap://") and USE_STARTTLS:
            conn.start_tls_s()

        # Bind using UPN (user@domain)
        try:
            conn.simple_bind_s(username, password)
        except ldap.INVALID_CREDENTIALS:
            # 701 – your code's message map
            message = get_response_message(request, 701)
            raise ValidationError2(message)
        except (ldap.SERVER_DOWN, ldap.LDAPError):
            message = get_response_message(request, 777)
            raise ValidationError2(message)

        # ---- Search current user entry to read tab number ----
        # Try multiple attributes; prefer env-defined TAB_ATTR first.
        requested_attrs = ["postalCode"]

        # Find by either UPN or sAMAccountName
        # Use ldap.filter.escape_filter_chars if you allow special chars (sam is from input)
        sam = username.split('@', 1)[0]
        f_upn = escape_filter_chars(username)
        f_sam = escape_filter_chars(sam)

        filter_str = f"(|(userPrincipalName={f_upn})(sAMAccountName={f_sam}))"

        results = conn.search_s(
            BASE_DN,
            ldap.SCOPE_SUBTREE,
            filterstr=filter_str,
            attrlist=requested_attrs
        )

        if not results:
            # Auth succeeded but user not found in directory subtree (OU scoping?)
            raise ValidationError2("Authenticated, but directory entry not found (check LDAP_BASE_DN / OU scope).")

        # Take the first matching entry
        _dn, attrs = results[0]

        # python-ldap returns bytes; decode first non-empty attribute in our priority list
        pinfl = None
        for attr in requested_attrs:
            val = attrs.get(attr)
            if val:
                # val is a list of byte strings; pick first
                pinfl = (val[0].decode("utf-8", "ignore") if isinstance(val[0], bytes) else str(val[0])).strip()
                if pinfl:
                    break

        if not pinfl:
            raise ValidationError2("Your directory entry has no tab number attribute set.")

        # ---- Find local Django user by tab number and return it ----
        # Adjust field name: assuming `User` has `tab_number` field
        user = User.objects.filter(pinfl=pinfl, is_user_active=True).first()
        if not user:
            # You can choose to auto-provision here if desired.
            # For now, mirror your old behavior:
            raise ValidationError2("Local user with this tab number not found or inactive.")

        return user

    finally:
        if conn is not None:
            try:
                conn.unbind_s()
            except Exception:
                pass
