from utils.db_connection import oracle_connection, db_column_name
from apps.company.models import Position


def run():
    """
    This script imports current active positions from the hr_s_posts table
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    updated_position_count = 0
    position_count = 0

    sql = "Select post_id, code, lavel_code, post_name, active_flag From ibs.hr_s_posts"
    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)

    if cur:
        for row in cur:
            active_flag = row[field_map['ACTIVE_FLAG']]

            try:
                position = Position.objects.get(iabs_post_id=row[field_map['POST_ID']])
                position.code = row[field_map['CODE']]
                position.iabs_level_code = row[field_map['LAVEL_CODE']]
                position.name = row[field_map['POST_NAME']]
                position.name_uz = row[field_map['POST_NAME']]
                position.name_ru = row[field_map['POST_NAME']]
                position.condition = 'A' if active_flag == 'Y' else 'P'
                position.save()
                updated_position_count += 1
            except Position.DoesNotExist:
                position = Position(
                    iabs_post_id=row[field_map['POST_ID']],
                    code=row[field_map['CODE']],
                    iabs_level_code=row[field_map['LAVEL_CODE']],
                    name=row[field_map['POST_NAME']],
                    condition='A' if active_flag == 'Y' else 'P'
                )
                position.name_ru = row[field_map['POST_NAME']]
                position.name_uz = row[field_map['POST_NAME']]
                position.save()
                position_count += 1

    else:
        pass

    cursor.close()
    conn.close()

    print('created position count ', position_count)
    print('updated position count ', updated_position_count)
