from utils.db_connection import oracle_connection, db_column_name
from apps.company.models import Company


def run():
    """
    This script imports branches from the HR_S_FILIALS_ORDERS_V
    from iabs database to the Company model in the company app.
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    filial_count = 0

    sql = "Select code, local_code, text From ibs.hr_s_filials_orders_v"
    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)
    filial_count += 1
    uptaded_count = 0
    if cur:
        for row in cur:

            try:
                company = Company.objects.get(local_code=row[field_map['LOCAL_CODE']])
                # company.code = row[field_map['CODE']]
                # company.name = row[field_map['TEXT']]
                # company.save()
                uptaded_count += 1
            except Company.DoesNotExist:
                Company.objects.create(
                    code=row[field_map['CODE']],
                    name=row[field_map['TEXT']],
                    local_code=row[field_map['LOCAL_CODE']],
                    condition='A'
                )
                filial_count += 1
    else:
        pass

    cursor.close()
    conn.close()

    print('filial count ', filial_count)
    print('updated count ', uptaded_count)
