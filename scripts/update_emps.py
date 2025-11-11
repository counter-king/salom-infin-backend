from utils.db_connection import oracle_connection, db_column_name
from apps.user.models import User, UserStatus
from apps.company.models import Department


def get_department_id(department_code, company_id):
    try:
        return Department.objects.get(code=department_code, company_id=company_id).id
    except Department.DoesNotExist:
        return None


def get_top_level_department_id(department_code, company_id):
    try:
        department = Department.objects.get(code=department_code, company_id=company_id)
        if department.parent:
            return get_top_level_department_id(department.parent.code, company_id)
        else:
            return department.id
    except Department.DoesNotExist:
        return None


def run():
    success_count = 0
    fail_count = 0
    multiple_users = []

    conn = oracle_connection()
    cursor = conn.cursor()

    sql = "select he.Emp_Id, he.Staffing_Id, he.Department_Code, he.Dep_Parent_Code from ibs.hr_emps_v he where he.Condition not in ('P', 'KP', 'PO', 'KO')"

    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)

    if cur:
        for row in cur:
            emp_id = row[field_map['EMP_ID']]
            department_code = row[field_map['DEPARTMENT_CODE']]
            dep_parent_code = row[field_map['DEP_PARENT_CODE']]

            try:
                user = User.objects.get(iabs_emp_id=emp_id)
                user.department_id = get_department_id(department_code, user.company_id)
                user.top_level_department_id = get_top_level_department_id(department_code, user.company_id)
                user.save()
                success_count += 1
            except User.MultipleObjectsReturned:
                multiple_users.append(emp_id)
                fail_count += 1

            except User.DoesNotExist:
                fail_count += 1


    cursor.close()
    conn.close()

    print('success count ', success_count)
    print('fail count ', fail_count)
    print('multiple users ', multiple_users)
