from utils.db_connection import oracle_connection, db_column_name
from apps.company.models import Department


def run():
    """
    This script imports sub and sub departments from the HR_DEPARTMENTS
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    created_count = 0
    updated_count = 0
    for dept in Department.objects.filter(parent__isnull=True):
        for sub_dept in Department.objects.filter(parent_id=dept.id):
            sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.LEV From ibs.hr_departments_v h where h.Parent_Code=:1 and h.Condition in ('A', 'K') and h.Local_Code=:2"
            cursor.execute(sql, (sub_dept.code, sub_dept.company.local_code))
            cur = cursor.fetchall()
            field_map = db_column_name(cursor)

            if cur:
                for row in cur:
                    old_dept = Department.objects.filter(code=row[field_map['CODE']])
                    if old_dept.first():
                        old_dept_obj = old_dept.first()
                        old_dept_obj.level = row[field_map['LEV']]
                        old_dept_obj.company_id = sub_dept.company_id
                        old_dept_obj.save()
                        updated_count += 1
                    else:
                        Department.objects.create(
                            code=row[field_map['CODE']],
                            parent_code=row[field_map['PARENT_CODE']],
                            name=row[field_map['DEPARTMENT_NAME']],
                            name_uz=row[field_map['DEPARTMENT_NAME']],
                            name_ru=row[field_map['DEPARTMENT_NAME']],
                            name_en=row[field_map['DEPARTMENT_NAME']],
                            company_id=sub_dept.company_id,
                            parent_id=sub_dept.id,
                            condition='A',
                            level=row[field_map['LEV']]
                        )
                        created_count += 1
            else:
                pass

    cursor.close()
    conn.close()

    print('updated count ', updated_count)
    print('created count ', created_count)
