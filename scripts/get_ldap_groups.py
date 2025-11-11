import os
from ldap3 import Server, Connection, ALL, SUBTREE

# Define your AD server and credentials
server_address = os.getenv('LDAP_HOST')  # e.g., 'ldap://yourdomain.com'
username = os.getenv('LDAP_LOGIN')  # e.g., 'CN=Administrator,CN=Users,DC=example,DC=com'
password = os.getenv('LDAP_PASSWORD')
COMPANY = os.getenv('COMPANY')

# Create a connection to the server
server = Server(server_address, get_info=ALL)
conn = Connection(server, user=username, password=password, auto_bind=True)

# Set up the search parameters
search_base = f'DC={COMPANY},DC=uz'  # Change to your domain base DN
search_filter = '(objectClass=group)'  # Filter to find all groups
search_scope = SUBTREE

# Perform the search
conn.search(search_base, search_filter, search_scope, attributes=['cn'])

# Print the results
for entry in conn.entries:
    print(f"Group DN: {entry.entry_dn}")
    print(f"Group Name: {entry.cn.value}")

# Unbind the connection
conn.unbind()
