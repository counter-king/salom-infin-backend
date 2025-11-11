import logging

from django.db import transaction

from apps.company.models import Department, Company, Position
from utils.db_connection import db_column_name, oracle_connection
from utils.tools import get_children

from celery import shared_task


def recalculate_sub_department_count(department_id):
    """
    Recalculate the sub-department counts for a department and its ancestors.
    """
    try:
        department = Department.objects.get(id=department_id)
    except Department.DoesNotExist:
        print(f"Department with ID {department_id} does not exist.")
        return

    # Recalculate sub-department count for the current department
    all_descendant_ids = get_children(Department, department_id)
    department.sub_department_count = len(all_descendant_ids)
    department.save()

    # Propagate updates to ancestors
    parent = department.parent
    while parent:
        all_descendant_ids = get_children(Department, parent.id)
        parent.sub_department_count = len(all_descendant_ids)
        parent.save()
        parent = parent.parent


@shared_task
def update_company_branches():
    """
    This script imports branches from the HR_S_FILIALS_ORDERS_V
    from iabs database to the Company model in the company app.
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    sql = "Select code, local_code, text From ibs.hr_s_filials_orders_v"
    cursor.execute(sql)
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)
    filial_count = 0
    updated_count = 0
    if cur:
        for row in cur:
            try:
                company = Company.objects.get(local_code=row[field_map['LOCAL_CODE']])
                # company.name = row[field_map['TEXT']]
                # company.name_ru = row[field_map['TEXT']]
                # company.name_uz = row[field_map['TEXT']]
                # company.code = row[field_map['CODE']]
                updated_count += 1
            except Company.DoesNotExist:
                Company.objects.create(
                    code=row[field_map['CODE']],
                    name=row[field_map['TEXT']],
                    local_code=row[field_map['LOCAL_CODE']],
                    condition='A',
                    name_uz=row[field_map['TEXT']],
                    name_ru=row[field_map['TEXT']]
                )
                filial_count += 1
    else:
        pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")
    logging.info(f"filial count {filial_count}")


@shared_task
def update_positions():
    """
    Import positions from IBS.HR_S_POSTS into Position model.
    - Streams Oracle rows (constant memory)
    - Dedupes by post_id (latest row wins)
    - Bulk creates/updates only when fields changed
    """
    # 1) Stream rows from Oracle → source map (post_id -> fields)
    source_by_id = {}  # {post_id: {"code":..., "level":..., "name":..., "condition":...}}
    conn = oracle_connection()
    cursor = conn.cursor()
    ORACLE_FETCH_CHUNK = 1000
    BULK_CREATE_BATCH = 1000
    BULK_UPDATE_BATCH = 1000

    SQL_POSITIONS = "Select post_id, code, lavel_code, post_name, active_flag From ibs.hr_s_posts"
    # cursor.execute(sql)
    # cur = cursor.fetchall()
    # field_map = db_column_name(cursor)

    try:
        cursor.arraysize = ORACLE_FETCH_CHUNK
        cursor.execute(SQL_POSITIONS)
        fm = db_column_name(cursor)  # e.g. {"POST_ID":0,"CODE":1,"LAVEL_CODE":2,"POST_NAME":3,"ACTIVE_FLAG":4}

        for r in cursor:
            post_id = r[fm["POST_ID"]]
            if post_id is None:
                continue
            name = (r[fm["POST_NAME"]] or "").strip()
            code = (r[fm["CODE"]] or "").strip()
            level = (r[fm["LAVEL_CODE"]] or "").strip()
            active_flag = (r[fm["ACTIVE_FLAG"]] or "").strip().upper()
            condition = "A" if active_flag == "Y" else "P"

            source_by_id[int(post_id)] = {
                "code": code,
                "level": level,  # maps to Position.iabs_level_code
                "name": name,
                "condition": condition,
            }
    finally:
        cursor.close()
        conn.close()

    if not source_by_id:
        msg = "Positions sync: no rows from Oracle."
        logging.info(msg)
        return msg

    # 2) Load existing positions for those ids (one per iabs_post_id)
    existing_qs = (
        Position.objects
        .filter(iabs_post_id__in=source_by_id.keys())
        .order_by("iabs_post_id", "-id")  # newest wins if duplicates exist
    )
    existing_by_id = {}
    for p in existing_qs.iterator(chunk_size=1000):
        if p.iabs_post_id not in existing_by_id:
            existing_by_id[p.iabs_post_id] = p

    # 3) Decide creates vs updates (avoid unnecessary writes)
    to_create = []
    to_update = []
    fields = ["code", "iabs_level_code", "name", "name_uz", "name_ru", "condition"]

    for post_id, src in source_by_id.items():
        existing = existing_by_id.get(post_id)
        if not existing:
            to_create.append(Position(
                iabs_post_id=post_id,
                code=src["code"],
                iabs_level_code=src["level"],
                name=src["name"],
                name_uz=src["name"],
                name_ru=src["name"],
                condition=src["condition"],
            ))
        else:
            changed = False
            if existing.code != src["code"]:
                existing.code = src["code"]
                changed = True
            if existing.iabs_level_code != src["level"]:
                existing.iabs_level_code = src["level"]
                changed = True
            if existing.name != src["name"]:
                existing.name = src["name"]
                existing.name_ru = src["name"]
                existing.name_uz = src["name"]
                changed = True
            if existing.condition != src["condition"]:
                existing.condition = src["condition"]
                changed = True

            if changed:
                to_update.append(existing)

    # 4) Bulk create/update in batches
    created_n = 0
    updated_n = 0
    with transaction.atomic():
        if to_create:
            Position.objects.bulk_create(to_create, batch_size=BULK_CREATE_BATCH)
            created_n = len(to_create)
        if to_update:
            Position.objects.bulk_update(to_update,
                                         fields=fields,
                                         batch_size=BULK_UPDATE_BATCH)
            updated_n = len(to_update)

    msg = f"Positions sync: {created_n} created, {updated_n} updated, {len(source_by_id)} total."
    logging.info(msg)
    return msg

    # TODO: Old implementation, remove after testing
    # if cur:
    #     for row in cur:
    #         active_flag = row[field_map['ACTIVE_FLAG']]
    #
    #         try:
    #             position = Position.objects.get(iabs_post_id=row[field_map['POST_ID']])
    #             position.name = row[field_map['POST_NAME']]
    #             position.name_ru = row[field_map['POST_NAME']]
    #             position.name_uz = row[field_map['POST_NAME']]
    #             position.code = row[field_map['CODE']]
    #             position.iabs_level_code = row[field_map['LAVEL_CODE']]
    #             position.condition = 'A' if active_flag == 'Y' else 'P'
    #             position.save()
    #             updated_position_count += 1
    #         except Position.DoesNotExist:
    #             position = Position(
    #                 iabs_post_id=row[field_map['POST_ID']],
    #                 code=row[field_map['CODE']],
    #                 iabs_level_code=row[field_map['LAVEL_CODE']],
    #                 name=row[field_map['POST_NAME']],
    #                 name_ru=row[field_map['POST_NAME']],
    #                 name_uz=row[field_map['POST_NAME']],
    #                 condition='A' if active_flag == 'Y' else 'P'
    #             )
    #             position.save()
    #             position_count += 1
    #
    # else:
    #     pass
    #
    # cursor.close()
    # conn.close()
    #
    # logging.info(f"updated position count {updated_position_count}")
    # logging.info(f"position count {position_count}")


@shared_task
def update_iabs_dep_id():
    """
    This script imports iabs department id from the HR_DEPARTMENTS
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    updated_count = 0
    for dept in Department.objects.filter(iabs_dept_id__isnull=True):
        sql = "Select h.Dep_Id From ibs.hr_departments_v h where h.Code=:1"
        cursor.execute(sql, (dept.code,))
        cur = cursor.fetchall()
        field_map = db_column_name(cursor)

        if cur:
            for row in cur:
                dept.iabs_dept_id = row[field_map['DEP_ID']]
                dept.save()
                updated_count += 1
        else:
            pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")


@shared_task
def update_top_level_departments():
    """
    This script imports top level departments from the HR_DEPARTMENTS
    from iabs database to the Department model in the company app.
    """
    conn = oracle_connection()
    cursor = conn.cursor()

    updated_count = 0
    created_count = 0
    # Get all companies to set their id as foreign key and filter for further queries
    companies = Company.objects.all()

    for company in companies:
        sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.Lev, h.Dep_Id From ibs.hr_departments_v h where h.Parent_Code='000000' and h.local_code=:1 and h.Condition in ('A', 'K')"
        cursor.execute(sql, (company.local_code,))
        cur = cursor.fetchall()
        field_map = db_column_name(cursor)
        if cur:
            for row in cur:
                old_dept = Department.objects.filter(code=row[field_map['CODE']], company_id=company.id).first()
                if old_dept:
                    old_dept.level = row[field_map['LEV']]
                    old_dept.name = row[field_map['DEPARTMENT_NAME']]
                    old_dept.name_ru = row[field_map['DEPARTMENT_NAME']]
                    old_dept.name_uz = row[field_map['DEPARTMENT_NAME']]
                    old_dept.iabs_dept_id = row[field_map['DEP_ID']]
                    old_dept.company_id = company.id
                    old_dept.save()
                    updated_count += 1
                else:
                    Department.objects.create(
                        code=row[field_map['CODE']],
                        parent_code=row[field_map['PARENT_CODE']],
                        name=row[field_map['DEPARTMENT_NAME']],
                        name_ru=row[field_map['DEPARTMENT_NAME']],
                        name_uz=row[field_map['DEPARTMENT_NAME']],
                        company_id=company.id,
                        condition='A',
                        level=row[field_map['LEV']],
                        iabs_dept_id=row[field_map['DEP_ID']]
                    )
                    created_count += 1
        else:
            pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")
    logging.info(f"created count {created_count}")


@shared_task
def update_sub_departments():
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
            sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.LEV, h.Dep_Id From ibs.hr_departments_v h where h.Parent_Code=:1 and h.local_code=:2 and h.Condition in ('A', 'K')"
            cursor.execute(sql, (dept.code, filial.local_code))
            cur = cursor.fetchall()
            field_map = db_column_name(cursor)

            if cur:
                for row in cur:
                    old_dept = Department.objects.filter(code=row[field_map['CODE']], company_id=filial.id)
                    if old_dept.exists():
                        old_dept_obj = old_dept.first()
                        old_dept_obj.level = row[field_map['LEV']]
                        old_dept_obj.name = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.name_ru = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.name_uz = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.company_id = filial.id
                        old_dept_obj.iabs_dept_id = row[field_map['DEP_ID']]
                        old_dept_obj.save()
                        updated_count += 1
                    else:
                        Department.objects.create(
                            code=row[field_map['CODE']],
                            parent_code=row[field_map['PARENT_CODE']],
                            name=row[field_map['DEPARTMENT_NAME']],
                            name_ru=row[field_map['DEPARTMENT_NAME']],
                            name_uz=row[field_map['DEPARTMENT_NAME']],
                            company_id=dept.company_id,
                            parent_id=dept.id,
                            condition='A',
                            level=row[field_map['LEV']],
                            iabs_dept_id=row[field_map['DEP_ID']]
                        )
                        created_count += 1
            else:
                pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")
    logging.info(f"created count {created_count}")
    logging.info(f"filial count {filial_count}")


@shared_task
def update_sub_sub_departments():
    """
    This script imports sub and sub departments from the HR_DEPARTMENTS
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    created_count = 0
    updated_count = 0
    for dept in Department.objects.filter(parent__isnull=True):
        for sub_dept in Department.objects.filter(parent_id=dept.id):
            sql = "Select h.Code, h.Parent_Code, h.Department_Name, h.LEV, h.Dep_Id From ibs.hr_departments_v h where h.Parent_Code=:1 and h.Condition in ('A', 'K') and h.Local_Code=:2"
            cursor.execute(sql, (sub_dept.code, sub_dept.company.local_code))
            cur = cursor.fetchall()
            field_map = db_column_name(cursor)

            if cur:
                for row in cur:
                    old_dept = Department.objects.filter(code=row[field_map['CODE']])
                    if old_dept.first():
                        old_dept_obj = old_dept.first()
                        old_dept_obj.level = row[field_map['LEV']]
                        old_dept_obj.name = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.name_ru = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.name_uz = row[field_map['DEPARTMENT_NAME']]
                        old_dept_obj.company_id = sub_dept.company_id
                        old_dept_obj.iabs_dept_id = row[field_map['DEP_ID']]
                        old_dept_obj.save()
                        updated_count += 1
                    else:
                        Department.objects.create(
                            code=row[field_map['CODE']],
                            parent_code=row[field_map['PARENT_CODE']],
                            name=row[field_map['DEPARTMENT_NAME']],
                            name_ru=row[field_map['DEPARTMENT_NAME']],
                            name_uz=row[field_map['DEPARTMENT_NAME']],
                            company_id=sub_dept.company_id,
                            parent_id=sub_dept.id,
                            condition='A',
                            level=row[field_map['LEV']],
                            iabs_dept_id=row[field_map['DEP_ID']]
                        )
                        created_count += 1
            else:
                pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")
    logging.info(f"created count {created_count}")


@shared_task
def update_department_status():
    """
    This script updates the status of departments
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    updated_count = 0
    for dept in Department.objects.filter(condition__in=('A', 'K')):
        sql = "Select h.Condition From ibs.hr_departments_v h where h.Dep_Id=:1"
        cursor.execute(sql, (dept.iabs_dept_id,))
        cur = cursor.fetchall()
        field_map = db_column_name(cursor)

        if cur:
            for row in cur:
                status = row[field_map['CONDITION']]
                dept.condition = 'A' if status in ['A', 'K'] else 'P'
                dept.save()
                updated_count += 1
        else:
            pass

    cursor.close()
    conn.close()

    logging.info(f"updated count {updated_count}")
