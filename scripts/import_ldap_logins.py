import os, ldap
from apps.user.models import User


def normalize_phone(phone):
    if len(phone) <= 4:
        return f'{phone[0]}{phone[1]}-{phone[2]}{phone[3]}'
    return None


def normalize_login(login):
    if login:
        return login.split('@')[0]
    return None


def run():
    HOST = os.environ.get('LDAP_HOST')
    LOGIN = os.environ.get('LDAP_LOGIN')
    PASSWORD = os.environ.get('LDAP_PASSWORD')
    con = ldap.initialize(HOST)

    # criteria = "(&(objectClass=user)(sAMAccountName=username))"
    # attributes = ['displayName', 'pager', 'mail']
    count = 0
    try:
        con.simple_bind_s(LOGIN, PASSWORD)
        res = con.search_s("CN=....REPUBLIC,DC=sqb,DC=uz", ldap.SCOPE_SUBTREE, '(objectClass=User)')

        for dn, entry in res:
            display_name = entry.get('displayName')
            email = entry.get('mail')
            pinfl = entry.get('pager')
            cisco = entry.get('telephoneNumber')

            if pinfl is not None:
                dp = str(display_name[0], 'utf-8')
                mail = str(email[0], 'utf-8')
                phone = str(cisco[0], 'utf-8')
                pinfl = str(pinfl[0], 'utf-8')
                count += 1
                print(dp, mail, phone, pinfl)
                # user = User.objects.filter(pinfl=pinfl).first()
                # if user:
                #     user.ldap_login = normalize_login(mail)
                #     user.email = mail
                #     user.cisco = normalize_phone(phone)
                #     user.normalized_cisco = phone
                #     user.save()
                #     count += 1
                #     print(dp)
    except Exception as error:
        print(error)

    print(count)
