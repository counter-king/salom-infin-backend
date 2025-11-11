from utils.db_connection import oracle_connection, db_column_name
from apps.company.models import Company, Department


def run():
    """
    This script imports sub departments of top level departments from the HR_DEPARTMENTS
    """
    conn = oracle_connection()
    cursor = conn.cursor()

    updated_count = 0
    created_count = 0
    filial_count = 0
    for filial in Company.objects.filter(condition='A'):
        filial_count += 1
        for dept in Department.objects.filter(company_id=filial.id, parent__isnull=True):
            sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.LEV From ibs.hr_departments_v h where h.Parent_Code=:1 and h.local_code=:2 and h.Condition in ('A', 'K')"
            cursor.execute(sql, (dept.code, filial.local_code))
            cur = cursor.fetchall()
            field_map = db_column_name(cursor)

            if cur:
                for row in cur:
                    old_dept = Department.objects.filter(code=row[field_map['CODE']])
                    if old_dept.exists():
                        old_dept_obj = old_dept.first()
                        old_dept_obj.level = row[field_map['LEV']]
                        old_dept_obj.company_id = filial.id
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
                            company_id=dept.company_id,
                            parent_id=dept.id,
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
    print('filial count ', filial_count)
