import uuid

from utils.db_connection import oracle_connection, db_column_name
from apps.user.models import User, UserStatus
from apps.company.models import Company, Position


def format_date(date):
    if date:
        return date.strftime('%Y-%m-%d')
    else:
        return None


def get_condition_id(condition):
    return UserStatus.objects.get(code=condition).id


def run():
    """
    This script imports current active positions from the hr_s_posts table
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    updated_user_count = 0
    new_added_user_count = 0
    failed_user_count = 0

    sql = "select he.emp_id, he.tab_num, he.last_name, he.first_name, he.middle_name, he.date_begin, he.staffing_id, he.condition, he.inps, he.inn,he.gender, he.birth_date, he.phone_mobil, hs.post_id, hs.local_code from ibs.hr_emps he, ibs.hr_staffing hs, ibs.hr_emp_works hw where he.emp_id = hw.emp_id and hw.work_now = 'Y' and hs.staffing_id = hw.staffing_id and he.condition not in ('P', 'KP', 'PO', 'KO')"

    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)

    if cur:
        for row in cur:
            user_status_id = get_condition_id(row[field_map['CONDITION']])
            birth_date_format = format_date(row[field_map['BIRTH_DATE']])
            begin_date_format = format_date(row[field_map['DATE_BEGIN']])

            try:
                position_id = Position.objects.get(iabs_post_id=row[field_map['POST_ID']]).id
            except Position.DoesNotExist:
                position_id = None

            try:
                company_id = Company.objects.get(local_code=row[field_map['LOCAL_CODE']]).id
            except Company.DoesNotExist:
                company_id = None

            try:
                user = User.objects.get(iabs_emp_id=row[field_map['EMP_ID']])
                user.table_number = row[field_map['TAB_NUM']]
                user.last_name = row[field_map['LAST_NAME']]
                user.first_name = row[field_map['FIRST_NAME']]
                user.father_name = row[field_map['MIDDLE_NAME']]
                user.birth_date = birth_date_format
                user.status_id = user_status_id
                user.position_id = position_id
                user.company_id = company_id
                user.begin_work_date = begin_date_format
                user.pinfl = row[field_map['INPS']]
                user.tin = row[field_map['INN']]
                user.iabs_staffing_id = row[field_map['STAFFING_ID']]
                user.save()
                updated_user_count += 1
            except User.MultipleObjectsReturned:
                failed_user_count += 1
                continue
            except User.DoesNotExist:
                user = User(
                    table_number=row[field_map['TAB_NUM']],
                    last_name=row[field_map['LAST_NAME']],
                    first_name=row[field_map['FIRST_NAME']],
                    father_name=row[field_map['MIDDLE_NAME']],
                    birth_date=birth_date_format,
                    status_id=user_status_id,
                    position_id=position_id,
                    company_id=company_id,
                    begin_work_date=begin_date_format,
                    pinfl=row[field_map['INPS']],
                    tin=row[field_map['INN']],
                    iabs_staffing_id=row[field_map['STAFFING_ID']],
                    iabs_emp_id=row[field_map['EMP_ID']],
                    gender=row[field_map['GENDER']],
                    phone=row[field_map['PHONE_MOBIL']],
                    username=uuid.uuid4(),
                )
                user.save()
                new_added_user_count += 1

    else:
        pass

    cursor.close()
    conn.close()

    print('updated user count ', updated_user_count)
    print('new added user count ', new_added_user_count)
    print('failed user count ', failed_user_count)
