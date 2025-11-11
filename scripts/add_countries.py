from apps.reference.models import Country
from utils.db_connection import oracle_connection, db_column_name


def run():
    """
    This script imports current active countries from the hr_s_posts table
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    updated_country_count = 0
    country_count = 0

    sql = "Select cc.code, cc.currency_code, cc.name, cc.char_ext_code, cc.char_code From ibs.ref_country_v cc where cc.condition='A'"
    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)

    if cur:
        for row in cur:
            try:
                country = Country.objects.get(code=row[field_map['CODE']])
                country.currency_code = row[field_map['CURRENCY_CODE']]
                country.name = row[field_map['NAME']]
                country.alpha_3 = row[field_map['CHAR_EXT_CODE']]
                country.alpha_2 = row[field_map['CHAR_CODE']]
                country.status = 'A'
                country.save()
                updated_country_count += 1
            except Country.DoesNotExist:
                country = Country(
                    code=row[field_map['CODE']],
                    currency_code=row[field_map['CURRENCY_CODE']],
                    name=row[field_map['NAME']],
                    alpha_3=row[field_map['CHAR_EXT_CODE']],
                    alpha_2=row[field_map['CHAR_CODE']],
                    status='A'
                )
                country.save()
                country_count += 1

    cursor.close()
    conn.close()

    print('created country count ', country_count)
    print('updated country count ', updated_country_count)
