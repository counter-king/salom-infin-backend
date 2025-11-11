from utils.db_connection import oracle_connection, db_column_name
from apps.company.models import Company, Department


# def run():
#     """
#     This script imports top level departments from the HR_DEPARTMENTS
#     from iabs database to the Department model in the company app.
#     """
#     conn = oracle_connection()
#     cursor = conn.cursor()
#
#     updated_count = 0
#     created_count = 0
#     # Get all companies to set their id as foreign key and filter for further queries
#     companies = Company.objects.all()
#
#     for company in companies:
#         sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.Lev From ibs.hr_departments_v h where h.Parent_Code='000000' and h.local_code=:1 and h.Condition in ('A', 'K')"
#         cursor.execute(sql, (company.local_code,))
#         cur = cursor.fetchall()
#         field_map = db_column_name(cursor)
#         if cur:
#             for row in cur:
#                 old_dept = Department.objects.filter(code=row[field_map['CODE']], company_id=company.id).first()
#                 if old_dept:
#                     old_dept.level = row[field_map['LEV']]
#                     old_dept.company_id = company.id
#                     old_dept.save()
#                     updated_count += 1
#                 else:
#                     Department.objects.create(
#                         code=row[field_map['CODE']],
#                         parent_code=row[field_map['PARENT_CODE']],
#                         name=row[field_map['DEPARTMENT_NAME']],
#                         company_id=company.id,
#                         condition='A',
#                         level=row[field_map['LEV']]
#                     )
#                     created_count += 1
#         else:
#             pass
#
#     cursor.close()
#     conn.close()
#
#     print('updated count ', updated_count)
#     print('created count ', created_count)


def run():
    """
    This script imports sub departments of top level departments from the HR_DEPARTMENTS
    """
    conn = oracle_connection()
    cursor = conn.cursor()

    updated_count = 0
    not_updated_count = 0
    parent_null = 0
    for filial in Company.objects.filter(condition='A'):
        for dept in Department.objects.filter(company_id=filial.id):
            sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.LEV, h.Dep_Id From ibs.hr_departments_v h where h.dep_id=:1 and h.local_code=:2 and h.Condition in ('A', 'K')"
            cursor.execute(sql, (dept.iabs_dept_id, filial.local_code))
            cur = cursor.fetchall()
            field_map = db_column_name(cursor)

            if cur:
                for row in cur:
                    old_dept_obj = Department.objects.filter(code=row[field_map['CODE']], company_id=filial.id).first()
                    parent_code = row[field_map['PARENT_CODE']]

                    if parent_code == '000000' and old_dept_obj and old_dept_obj.parent:
                        old_dept_obj.parent = None
                        old_dept_obj.save()
                        parent_null += 1
                        continue

                    if old_dept_obj:
                        old_dept_obj.level = row[field_map['LEV']]
                        old_dept_obj.code = row[field_map['CODE']]
                        old_dept_obj.parent_code = row[field_map['PARENT_CODE']]
                        # old_dept_obj.name = row[field_map['DEPARTMENT_NAME']]
                        # old_dept_obj.name_ru = row[field_map['DEPARTMENT_NAME']]
                        # old_dept_obj.name_uz = row[field_map['DEPARTMENT_NAME']]
                        # old_dept_obj.company_id = filial.id
                        # old_dept_obj.iabs_dept_id = row[field_map['DEP_ID']]
                        old_dept_obj.save()
                        updated_count += 1
                    else:
                        # Department.objects.create(
                        #     code=row[field_map['CODE']],
                        #     parent_code=row[field_map['PARENT_CODE']],
                        #     name=row[field_map['DEPARTMENT_NAME']],
                        #     name_ru=row[field_map['DEPARTMENT_NAME']],
                        #     name_uz=row[field_map['DEPARTMENT_NAME']],
                        #     company_id=dept.company_id,
                        #     parent_id=dept.id,
                        #     condition='A',
                        #     level=row[field_map['LEV']],
                        #     iabs_dept_id=row[field_map['DEP_ID']]
                        # )
                        not_updated_count += 1
            else:
                pass

    cursor.close()
    conn.close()

    print(f"updated count {updated_count}")
    print(f"not updated count {not_updated_count}")
    print(f"parent null count {parent_null}")
