import os
from ldap3 import Server, Connection, ALL, SUBTREE
from apps.user.models import User


def normalize_phone(phone):
    if phone is None:
        return None

    if len(phone) <= 4:
        return f'{phone[0]}{phone[1]}-{phone[2]}{phone[3]}'


def normalize_login(login):
    if login:
        return login.split('@')[0]
    return None


def run():
    # Define your AD server and credentials
    server_address = os.getenv('LDAP_HOST')  # e.g., 'ldap://yourdomain.com'
    username = os.getenv('LDAP_LOGIN')  # e.g., 'CN=Administrator,CN=Users,DC=example,DC=com'
    password = os.getenv('LDAP_PASSWORD')

    # Create a connection to the server
    server = Server(server_address, get_info=ALL)
    conn = Connection(server, user=username, password=password, auto_bind=True)

    # Define the OU DN and search filter to find all users in the OU
    ou_dn = 'OU=....REPUBLIC,DC=sqb,DC=uz'  # Replace with the distinguished name of your OU
    search_filter = '(objectClass=user)'  # Filter to find user objects
    search_scope = SUBTREE

    # Set page size
    page_size = 1000
    total_entries = 4000
    retrieved_entries = 0
    entries = []

    conn.search(ou_dn, search_filter, search_scope,
                attributes=['cn', 'sAMAccountName', 'mail', 'pager', 'telephoneNumber'],
                paged_size=page_size)
    count = 0
    while True:
        for entry in conn.entries:
            entries.append(entry)
            # print(f"CN: {entry.cn.value if entry.cn else None}")
            # print(f"sAMAccountName: {entry.sAMAccountName.value if entry.sAMAccountName else None}")
            # print(f"mail: {entry.mail.value if entry.mail else None}")
            # print(f"pager: {entry.pager.value if entry.pager else None}")
            # print(f"telephoneNumber: {entry.telephoneNumber.value if entry.telephoneNumber else None}")
            # print('-' * 40)
            # count += 1

            retrieved_entries += 1
            if retrieved_entries >= total_entries:
                break

        if retrieved_entries >= total_entries or not conn.result['controls']['1.2.840.113556.1.4.319']['value'][
            'cookie']:
            break

        # Fetch the next page of results
        conn.search(ou_dn, search_filter, search_scope,
                    attributes=['cn', 'sAMAccountName', 'mail', 'pager', 'telephoneNumber'],
                    paged_size=page_size,
                    paged_cookie=conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'])

    for entry in entries:
        pinfl = entry.pager.value

        if pinfl is not None:
            user = User.objects.filter(pinfl=str(pinfl)).first()
            if user:
                user.ldap_login = normalize_login(str(entry.mail.value))
                user.email = str(entry.mail.value)
                user.cisco = normalize_phone(str(entry.telephoneNumber.value))
                user.normalized_cisco = str(entry.telephoneNumber.value)
                user.save()
                count += 1
                print(count)

    # Unbind the connection
    conn.unbind()
    print(f"Total updated users: {count}")
