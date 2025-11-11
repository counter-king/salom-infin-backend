from utils.db_connection import oracle_connection, db_column_name
from apps.user.models import UserStatus


def run():
    """
    This script imports employee statuses from the hr_s_emp_conditions_v
    from iabs database to the UserStatus model in the user app.
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    status_count = 0

    sql = "Select condition, condition_note, condition_type, ord From hr_s_emp_conditions_v"
    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)
    status_count += 1
    if cur:
        for row in cur:
            if row[field_map['ORD']] != 6:
                UserStatus.objects.create(
                    code=row[field_map['CONDITION']],
                    name=row[field_map['CONDITION_NOTE']],
                    code_type=row[field_map['CONDITION_TYPE']],
                    sort_ord=row[field_map['ORD']]
                )
                status_count += 1
    else:
        pass

    cursor.close()
    conn.close()

    print('status count ', status_count)
