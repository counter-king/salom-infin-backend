import datetime
import logging
from datetime import date, timedelta

from celery import shared_task

from apps.company.models import Company, Department
from apps.core.models import SQLQuery
from apps.core.services import effective_branch_managers, effective_department_managers
from apps.hr.models import Payroll, PayrollSubCategory, AttendanceExceptionApproval, AttendanceException
from apps.hr.services.payroll_generator import upsert_cells_for_date
from utils.db_connection import oracle_connection, db_column_name

subcat_cache = {}


def get_dept_ids(code, company=None):
    try:
        # Prefetch parent and parent's parent in a single query
        department = (Department.objects
                      .select_related('parent', 'parent__parent')
                      .get(code=code, company_id=company.id))

        sub_sub_dept_id = department.id
        sub_dept_id = department.parent.id if department.parent else None
        top_level_dept_id = department.parent.parent.id if department.parent and department.parent.parent else (
                sub_dept_id or sub_sub_dept_id
        )

        return top_level_dept_id, sub_dept_id, sub_sub_dept_id

    except Department.MultipleObjectsReturned:
        print("[WARN] Multiple departments found for code:", code)
        return None, None, None

    except Department.DoesNotExist:
        print(f"[WARN] Department not found for code: {code}")
        try:
            print(f"[INFO] Attempting to find top level department for company: {company.name}")
            top_level = Department.objects.get(code=company.local_code, company_id=company.id)
            return top_level.id, None, None
        except Department.DoesNotExist:
            print(f"[WARN] Top level department not found for local_code: {company.local_code}")
            return None, None, None


def get_company_id(local_code):
    """Returns the company ID for a given code."""
    try:
        company = Company.objects.get(local_code=local_code)
        return company
    except Company.MultipleObjectsReturned:
        print(f"[WARN] Multiple companies found for local_code: {local_code}")
    except Company.DoesNotExist:
        print(f"[WARN] Company not found for local_code: {local_code}")
        return None


def get_payroll_sub_category_id(name):
    """Returns the payroll subcategory ID for a given name."""
    if name in subcat_cache:
        return subcat_cache[name]
    try:
        subcat = PayrollSubCategory.objects.get(name=name)
        subcat_cache[name] = subcat.id
        return subcat.id
    except PayrollSubCategory.DoesNotExist:
        print(f"[WARN] Subcategory not found for name: {name}")
        return None


@shared_task
def fetch_payroll_data():
    """
    Fetches payroll data from an Oracle database,
    processes the data, and inserts it into the Payroll table.

    Summary:
    This task connects to an Oracle database to execute an SQL query
    aimed at retrieving payroll data for the current month.
    The data is then processed to map the necessary fields to the Payroll data model and bulk-inserted
    into the corresponding database table. If data integrity issues are encountered
    (such as missing company or pay type), those specific rows are skipped.
    Detailed logging is maintained throughout the task's execution.

    Returns:
        str: A summary message indicating the number of records successfully inserted
        and the number of rows that were skipped due to missing data.

    Exceptions:
        If a connection to the Oracle database fails, the task logs
        and returns an error message including the connection error details.
        If the SQL query execution fails, the task logs and
        returns an error message including the query execution error details.
        If the bulk insertion into the Payroll table fails, the task logs and
        returns an error message including the bulk insertion failure details.

    Notes:
        The function ensures the database connection and cursor are properly closed after use,
        even if an error occurs during the task's execution.

    @raises Exception: Logs and returns the error
    if any failure occurs during any stage of database connection,
    querying, or data insertion.
    """
    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except Exception as e:
        logging.error(f'[ERROR] Failed to connect to Oracle: {e}')
        return f'[ERROR] Failed to connect to Oracle: {e}'

    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_month.replace(day=1)
    formatted = first_day_last_month.strftime('%d.%m.%Y')

    try:
        raw_sql = SQLQuery.objects.get(query_type='monthly_payroll').sql_query
        last_month_str = f'{formatted}'
        cursor.execute(raw_sql, (last_month_str,))
        rows = cursor.fetchall()
        field_map = db_column_name(cursor)
    except Exception as e:
        logging.error(f'[ERROR] SQL query failed: {e}')
        return f'[ERROR] SQL query failed: {e}'

    count = 0
    skipped = 0
    payroll_data = []

    for row in rows:
        company = get_company_id(row[field_map['LOCAL_CODE']])
        top_level_dept_id, sub_dept_id, sub_sub_dept_id = get_dept_ids(row[field_map['DEP']], company)
        pay_type_id = get_payroll_sub_category_id(row[field_map['PAY_TYPE']])

        if not all([company.id, pay_type_id]):
            logging.info(f"[WARN] Missing company or pay type for row: {row}")
            skipped += 1
            continue

        payroll = Payroll(
            company_id=company.id,
            pay_type_id=pay_type_id,
            period=row[field_map['PERIOD']],
            amount=row[field_map['TOTAL']],
            department_id=top_level_dept_id,
            sub_department_id=sub_dept_id,
            division_id=sub_sub_dept_id,
        )
        payroll_data.append(payroll)
        count += 1

    try:
        Payroll.objects.bulk_create(payroll_data)
    except Exception as e:
        logging.error(f'[ERROR] Failed during bulk_create: {e}')
        return f'[ERROR] Failed during bulk_create: {e}'
    finally:
        cursor.close()
        conn.close()

    return f'Inserted {count} records into Payroll table, skipped {skipped} due to missing data.'


@shared_task
def create_attendance_exc_approval(exception_id: int, org_id: int, org_typ: str):
    """
    If an employee submits the appeal about attendance exception
    First, their director should approve or reject the appeal
    """

    if org_typ == 'branch':
        manager = effective_branch_managers(branch_id=org_id).first()
    else:
        manager = effective_department_managers(department_id=org_id).first()

    if not manager or not manager.user_id:
        # Fallback: optionally route to HR queue head, or skip creating an approval
        return f"No manager found for {exception_id}"

    AttendanceExceptionApproval.objects.create(
        exception_id=exception_id,
        user_id=manager.user_id,
        type='manager'
    )
    attendance = AttendanceException.objects.get(id=exception_id)
    attendance.manager_id = manager.user_id
    attendance.save()


@shared_task
def build_today_payroll_table():
    # Run daily between 22:00–23:00 by beat
    today = date.today()
    return upsert_cells_for_date(today)


@shared_task
def recheck_yesterday_payroll_table():
    # Run daily around 02:00–03:00 by beat
    yday = date.today() - datetime.timedelta(days=1)
    return upsert_cells_for_date(yday)
