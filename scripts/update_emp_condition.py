from apps.user.models import User, UserStatus
from utils.constants import CONSTANTS
from utils.db_connection import oracle_connection


def get_code_id(code):
    if code:
        code_obj = UserStatus.objects.get(code=code)
        return code_obj.id
    return None


def run():
    conn = oracle_connection()
    cursor = conn.cursor()
    user_count = 0
    resigned_count = 0

    for user in User.objects.filter(status__code__in=CONSTANTS.USER_STATUSES.CONDITIONS):

        sql = "Select distinct(he.emp_id), condition, work_now, condition_name, last_update_date From ibs.hr_emps_v he, ibs.hr_emp_works hw where he.emp_id = hw.emp_id and he.emp_id = :1 order by last_update_date desc"
        cursor.execute(sql, (user.iabs_emp_id,))
        res = cursor.fetchall()
        if res:
            user.status_id = get_code_id(res[0][1])

            if res[0][1] == 'P':
                user.is_user_active = False
                resigned_count += 1
            else:
                user.is_user_active = True

            user.save()
            user_count += 1
        else:
            pass

    cursor.close()
    conn.close()

    print('User count: ', user_count)
    print('Resigned count: ', resigned_count)
