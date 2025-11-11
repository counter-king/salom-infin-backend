import logging
import os
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Tuple, Iterable, Sequence, Any

from _ldap import LDAPError
from celery import shared_task
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from ldap3 import Server, Connection, ALL, SUBTREE

from apps.company.models import Position, Company, Department
from apps.user.batch_process import (
    _process_emp_dept_batch,
    _process_emp_rank_batch,
    _process_user_condition_batch,
    _update_user_leave_end_date,
)
from apps.user.models import User
from apps.user.serializers import UserSearchSerializer
from apps.user.services import (
    _normalize_phone,
    _unique_username,
    existing_usernames,
    existing_users_by_emp,
    format_date,
    get_condition_id,
    get_dept_ids,
    normalize_login,
    normalize_phone,
    parse_sick_leave_row,
    parse_trip_row,
    parse_vacation_row,
    smart_title,
    update_and_count,
)
from utils.constant_ids import user_search_status_ids
from utils.db_connection import oracle_connection, db_column_name
from utils.tools import get_current_date, send_sms_to_phone, _get_oracle_sql
from utils.utils import fmt_d, to_py_date


def username_count(phone):
    return User.objects.filter(username=phone).count()


def manual_update_user(emp_id):
    """
    Import from IABS database
    """
    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except IntegrityError as e:
        return _, f'Error connecting to Oracle database {e}'

    updated_user_count = 0

    sql = "select he.emp_id, he.tab_num, he.last_name, he.first_name, he.middle_name, he.date_begin, he.staffing_id, he.condition, he.inps, he.inn,he.gender, he.birth_date, he.phone_mobil, hs.post_id, hs.local_code, he.passport_seria, he.passport_number, he.passport_issued, he.passport_date_begin, he.passport_date_end from ibs.hr_emps he, ibs.hr_staffing hs, ibs.hr_emp_works hw where he.emp_id =:1 and he.emp_id = hw.emp_id and hw.work_now = 'Y' and hs.staffing_id = hw.staffing_id and he.condition not in ('P', 'PF', 'PO', 'KP', 'KO')"

    cursor.execute(sql, (emp_id,))
    cur = cursor.fetchall()
    field_map = db_column_name(cursor)

    if cur:
        for row in cur:
            user_status_id = get_condition_id(row[field_map['CONDITION']])
            birth_date_format = format_date(row[field_map['BIRTH_DATE']])
            begin_date_format = format_date(row[field_map['DATE_BEGIN']])
            passport_seria = row[field_map['PASSPORT_SERIA']]
            passport_number = row[field_map['PASSPORT_NUMBER']]
            passport_issued_by = row[field_map['PASSPORT_ISSUED']]
            passport_issue_date = None
            passport_expiry_date = None

            if row[field_map['PASSPORT_DATE_BEGIN']]:
                passport_issue_date = format_date(row[field_map['PASSPORT_DATE_BEGIN']])

            if row[field_map['PASSPORT_DATE_END']]:
                passport_expiry_date = format_date(row[field_map['PASSPORT_DATE_END']])

            try:
                position_id = Position.objects.get(iabs_post_id=row[field_map['POST_ID']]).id
            except Position.DoesNotExist:
                position_id = None

            try:
                company_id = Company.objects.get(local_code=row[field_map['LOCAL_CODE']]).id
            except Company.DoesNotExist:
                company_id = None

            phone = row[field_map['PHONE_MOBIL']]
            user = User.objects.get(iabs_emp_id=row[field_map['EMP_ID']], is_user_active=True)
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
            user.username = phone
            user.phone = phone
            user.passport_seria = passport_seria
            user.passport_number = passport_number
            user.passport_issued_by = passport_issued_by
            user.passport_issue_date = passport_issue_date
            user.passport_expiry_date = passport_expiry_date
            user.save()
            updated_user_count += 1
    else:
        pass

    update_employee_department(emp_id=emp_id)

    cursor.close()
    conn.close()

    if updated_user_count > 0:
        return 'ok', 'User updated successfully'
    else:
        return "error", 'User not found or no changes made'


SQL_LEAVE_ENDS_FROM = """
                      select T.emp_id, T.date_end
                      from IBS.HR_EMP_VACATION_V T
                      where T.date_end >= to_date(:1, 'DD.MM.YYYY')
                      """

TRIP_END_SQL = """ SELECT He.emp_id, ht.date_begin, ht.date_end
                   from ibs.hr_emps he,
                        ibs.hr_emp_trips_v ht
                   WHERE he.condition = 'K'
                     and ht.emp_id = he.emp_id
                     and sysdate BETWEEN ht.date_begin and ht.date_end"""


@shared_task
def save_leave_end_date() -> str:
    """
    Update User.leave_end_date from Oracle HR_EMP_VACATION_V for all rows with Date_End >= today.
    - Streams Oracle results (no fetchall)
    - Keeps the LATEST end date per employee
    - Performs batched CASE/WHEN updates against User by iabs_emp_id
    """
    BATCH_SIZE = 500  # Number of users to update in one query

    # 1) Open Oracle
    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except Exception as e:
        logging.error("Error connecting to Oracle database: %s", e, exc_info=True)
        return f"Error connecting to Oracle database {e}"

    today = get_current_date()
    today_str = fmt_d(today)

    processed_vac = processed_trip = 0
    updated_total = missing_users_total = unique_empids_total = 0

    # 2) Stream rows → build per-batch map: emp_id -> max(end_date)
    emp_to_end: Dict[int, date] = {}

    def _flush_batch():
        nonlocal updated_total, missing_users_total, unique_empids_total
        if len(emp_to_end) >= BATCH_SIZE:
            u, miss = _update_user_leave_end_date(emp_to_end, today)
            updated_total += u
            missing_users_total += miss
            unique_empids_total += len(emp_to_end)
            emp_to_end.clear()

    try:
        # 2) Vacation stream
        try:
            cursor.execute(SQL_LEAVE_ENDS_FROM, (today_str,))
            fm = db_column_name(cursor)  # e.g., {"EMP_ID": 0, "DATE_END": 1}
        except Exception as e:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
            logging.error("Error executing Oracle query: %s", e, exc_info=True)
            return f"Error executing Oracle query: {e}"

        for row in cursor:
            processed_vac += 1
            try:
                emp_id = row[fm["EMP_ID"]]
                end_dt = to_py_date(row[fm["DATE_END"]])
                if end_dt is None:
                    continue
                prev = emp_to_end.get(emp_id)
                if prev is None or end_dt > prev:
                    emp_to_end[emp_id] = end_dt
            except Exception as row_err:
                logging.error("Vacation row parse failed: %s", row_err, exc_info=True)
                continue

            _flush_batch()

        # 3) TRIP stream (currently active trips)
        try:
            cursor.execute(TRIP_END_SQL)
            fm2 = db_column_name(cursor)  # e.g., {"EMP_ID": 0, "DATE_END": 1}
        except Exception as e:
            logging.error("Error executing trip query: %s", e, exc_info=True)
            return f"Error executing trip query: {e}"

        for row in cursor:
            processed_trip += 1
            try:
                emp_id = row[fm2["EMP_ID"]]
                end_dt = to_py_date(row[fm2["DATE_END"]])
                if end_dt is None:
                    continue
                prev = emp_to_end.get(emp_id)
                if prev is None or end_dt > prev:
                    emp_to_end[emp_id] = end_dt
            except Exception as row_err:
                logging.error("Trip row parse failed: %s", row_err, exc_info=True)
                continue

            _flush_batch()

        # Final flush (if anything remains)
        if emp_to_end:
            u, miss = _update_user_leave_end_date(emp_to_end, today)
            updated_total += u
            missing_users_total += miss
            unique_empids_total += len(emp_to_end)
            emp_to_end.clear()
    except Exception as e:
        logging.error("Error processing Oracle rows: %s", e, exc_info=True)
        return f"Error processing Oracle rows: {e}"
    else:
        msg = (
            f"leave_end_date sync: processed_vac={processed_vac}, processed_trip={processed_trip}, "
            f"distinct_emp_ids={unique_empids_total}, updated_rows={updated_total}, "
            f"missing_users={missing_users_total}, from={today_str}"
        )
        logging.info(msg)
        return msg
    finally:
        cursor.close()
        conn.close()


VACATION_KIND: Dict[str, Dict[str, Any]] = {
    # Unpaid leave (OB) – notify when it ENDS (return on next operational day)
    "unpaid_end": {
        "join": "join IBS.HR_EMPS HE on HE.Emp_ID = T.Emp_ID",
        "where": "HE.CONDITION = 'OB'",
        "date_col": "DATE_END",
        "needs_oper_day_return": True,  # include next operational day in SMS
        "message": (
            "Hurmatli xodim! Sizning shaxsiy arizangiz asosida berilgan ta'til muddati "
            "yakuniga yetdi. Ishga chiqish sanangiz: {return_date}. Sizni ish joyingizda kutamiz!"
        ),
    },
    # Regular vacation (WORK) – notify when it ENDS (return on next operational day)
    "work_end": {
        "join": "",
        "where": "T.VACATION_TYPE = 'WORK'",
        "date_col": "DATE_END",
        "needs_oper_day_return": True,
        "message": (
            "Hurmatli xodim! Umid qilamiz, ta'tilingiz maroqli o'tdi. "
            "Ishga chiqish sanasi: {return_date}. Sizni kutamiz!"
        ),
    },
    # Regular vacation (WORK) – notify when it STARTS (personalized, include end date)
    "work_start": {
        "join": "",
        "where": "T.VACATION_TYPE = 'WORK'",
        "date_col": "DATE_BEGIN",
        "needs_oper_day_return": False,  # we don’t mention return day here
        "message": (
            "Salom, {first_name}! Sizning ta’tilingiz {start_date} dan {end_date} gacha davom etadi. "
            "Bu vaqtni o'zingiz va yaqinlaringiz bilan yaxshi o'tkazing!"
        ),
    },
}

OPER_DAY_SQL = "select t.oper_day, t.day_status from ibs.calendar t where t.oper_day = to_date(:1, 'dd.mm.yyyy')"

# We always select begin+end so “start” messages can include {end_date}
VACATION_SQL_BASE = "select T.emp_id, T.date_begin, T.date_end from IBS.HR_EMP_VACATION_V T {join} where {where} and T.{date_col} = to_date(:1, 'DD.MM.YYYY')"


@dataclass(frozen=True)
class VacationRec:
    emp_id: int
    date_begin: Optional[date]
    date_end: Optional[date]


def _next_operational_day(cursor, start: date) -> date:
    """
    Starting from `start`, walk forward until calendar.day_status == 1.
    Returns that operational day (Oracle DATE cast to Python date).
    """
    fm: Dict[str, int] = {}
    first = True
    d = start
    while True:
        d_str = fmt_d(d)
        cursor.execute(OPER_DAY_SQL, (d_str,))
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"No operation day found for {d_str}")
        if first:
            fm.update(db_column_name(cursor))  # {'OPER_DAY': i, 'DAY_STATUS': i}
            first = False
        day_status = row[fm["DAY_STATUS"]]
        if str(day_status) == "1":
            return to_py_date(row[fm["OPER_DAY"]])
        d = d + timedelta(days=1)


def _fetch_vacations(cursor, kind: str, target: date) -> List[VacationRec]:
    """
    Fetch vacations for `kind` that match the target day on its configured date_col.
    Returns list of dicts: {'emp_id', 'date_begin', 'date_end'} as Python dates.
    """
    cfg = VACATION_KIND[kind]
    sql = VACATION_SQL_BASE.format(join=cfg["join"], where=cfg["where"], date_col=cfg["date_col"])
    cursor.execute(sql, (fmt_d(target),))
    rows = cursor.fetchall()
    if not rows:
        return []
    fm = db_column_name(cursor)  # {'EMP_ID': i, 'DATE_BEGIN': i, 'DATE_END': i}
    out: List[VacationRec] = []
    for r in rows:
        out.append(
            VacationRec(
                emp_id=r[fm["EMP_ID"]],
                date_begin=to_py_date(r[fm["DATE_BEGIN"]]),
                date_end=to_py_date(r[fm["DATE_END"]]),
            )
        )
    return out


def _send_sms_batch(kind: str, ends_on: str = "today") -> str:
    """
    Generic engine:
      - choose target day (today/tomorrow)
      - compute next operational day (if needed)
      - fetch vacations for that day
      - bulk-load users, personalize & send SMS
    """
    if kind not in VACATION_KIND:
        raise ValueError(f"Unknown kind: {kind}")
    cfg = VACATION_KIND[kind]

    # 1) Oracle connection
    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except Exception as e:
        logging.error("Oracle connection error: %s", e, exc_info=True)
        return f"Oracle connection error: {e}"

    try:
        today = get_current_date()
        target_day = today if ends_on == "today" else (today + timedelta(days=1))

        # Only compute return day when message needs it
        return_day: Optional[date] = None
        if cfg["needs_oper_day_return"]:
            try:
                return_day = _next_operational_day(cursor, today + timedelta(days=1))
            except Exception as e:
                logging.error("Failed to compute next operational day: %s", e, exc_info=True)
                return f"Failed to compute next operational day: {e}"

        # 2) Fetch all matching vacations for target day
        vacations = _fetch_vacations(cursor, kind, target_day)
        if not vacations:
            msg = f"No users for kind={kind} on {ends_on} ({fmt_d(target_day)})."
            logging.info(msg)
            return msg

        # 3) Bulk-load users once
        status_ids = user_search_status_ids()
        emp_ids = {v.emp_id for v in vacations}
        users_by_emp = existing_users_by_emp(emp_ids,
                                             mode="status",
                                             status_ids=status_ids,
                                             fields=["first_name", "phone", "pk"])

        # 4) Compose and send
        sent = 0
        missing_user = 0
        for v in vacations:
            emp_id = v.emp_id
            user = users_by_emp.get(emp_id)
            if not user:
                missing_user += 1
                logging.warning("No user for emp_id=%s", emp_id)
                continue

            try:
                if kind == "work_start":
                    # Personalized start notice: includes end date from Oracle row
                    msg = VACATION_KIND[kind]["message"].format(
                        first_name=(user.first_name or "").strip(),
                        start_date=fmt_d(target_day),
                        end_date=fmt_d(v.date_end) if v.date_end else "",
                    )
                else:
                    # End notices: include return day (next operational day)
                    msg = VACATION_KIND[kind]["message"].format(
                        return_date=fmt_d(return_day) if return_day else ""
                    )

                if user.phone:
                    send_sms_to_phone(user.phone, msg)
                    sent += 1
                else:
                    logging.warning("User has no phone; emp_id=%s user_id=%s", emp_id, user.pk)

            except Exception as sms_err:
                logging.error("SMS send failed emp_id=%s user_id=%s: %s", emp_id, user.pk, sms_err, exc_info=True)

        summary = (
                f"kind={kind}, ends_on={ends_on}, targeted={len(vacations)}, sent={sent}, "
                f"missing_user={missing_user}, target_day={fmt_d(target_day)}"
                + (f", return_day={fmt_d(return_day)}" if return_day else "")
        )
        logging.info(summary)
        return summary

    except Exception as e:
        logging.error("Unhandled error in SMS engine: %s", e, exc_info=True)
        return f"Error executing SMS job: {e}"
    finally:
        cursor.close()
        conn.close()


@shared_task
def send_sms_to_users_on_unpaid_leave() -> str:
    # Original behavior matched “ends today”; switch to "tomorrow" if desired.
    return _send_sms_batch(kind="unpaid_end", ends_on="today")


@shared_task
def send_sms_to_users_on_vacation() -> str:
    return _send_sms_batch(kind="work_end", ends_on="today")


@shared_task
def send_sms_to_users_about_vacation() -> str:
    return _send_sms_batch(kind="work_start", ends_on="today")


@dataclass(frozen=True)
class EmpRow:
    emp_id: int
    tab_num: Optional[str]
    last_name: Optional[str]
    first_name: Optional[str]
    middle_name: Optional[str]
    date_begin: Optional[str]
    staffing_id: Optional[str]
    condition: Optional[str]
    inps: Optional[str]
    inn: Optional[str]
    gender: Optional[str]
    birth_date: Optional[str]
    phone: Optional[str]
    post_id: Optional[int]
    local_code: Optional[str]
    passport_seria: Optional[str]
    passport_number: Optional[str]
    passport_issued: Optional[str]
    passport_date_begin: Optional[str]
    passport_date_end: Optional[str]


ORACLE_FETCH_CHUNK = 1000  # how many Oracle rows to stream per round
BULK_CREATE_CHUNK = 1000  # how many users to create per DB round
BULK_UPDATE_CHUNK = 1000  # how many users to update per DB round

EMP_SQL = (
    "select he.emp_id, he.tab_num, he.last_name, he.first_name, he.middle_name, "
    "       he.date_begin, he.staffing_id, he.condition, he.inps, he.inn, "
    "       he.gender, he.birth_date, he.phone_mobil, hs.post_id, hs.local_code, "
    "       he.passport_seria, he.passport_number, he.passport_issued, "
    "       he.passport_date_begin, he.passport_date_end "
    "from   ibs.hr_emps he "
    "       join ibs.hr_emp_works hw on he.emp_id = hw.emp_id and hw.work_now = 'Y' "
    "       join ibs.hr_staffing hs on hs.staffing_id = hw.staffing_id "
    "where  he.condition not in ('P', 'PF', 'PO', 'KP', 'KO')"
)


def _stream_oracle_rows() -> Iterable[EmpRow]:
    conn = oracle_connection()
    cursor = conn.cursor()
    try:
        cursor.arraysize = ORACLE_FETCH_CHUNK
        cursor.execute(EMP_SQL)
        fm = db_column_name(cursor)  # e.g., {'EMP_ID': 0, ...}
        for r in cursor:
            yield EmpRow(
                emp_id=r[fm["EMP_ID"]],
                tab_num=r[fm["TAB_NUM"]],
                last_name=smart_title(r[fm["LAST_NAME"]]),
                first_name=smart_title(r[fm["FIRST_NAME"]]),
                middle_name=smart_title(r[fm["MIDDLE_NAME"]]),
                date_begin=format_date(r[fm["DATE_BEGIN"]]),
                staffing_id=r[fm["STAFFING_ID"]],
                condition=r[fm["CONDITION"]],
                inps=r[fm["INPS"]],
                inn=r[fm["INN"]],
                gender=r[fm["GENDER"]],
                birth_date=format_date(r[fm["BIRTH_DATE"]]),
                phone=_normalize_phone(r[fm["PHONE_MOBIL"]]),
                post_id=r[fm["POST_ID"]],
                local_code=r[fm["LOCAL_CODE"]],
                passport_seria=r[fm["PASSPORT_SERIA"]],
                passport_number=r[fm["PASSPORT_NUMBER"]],
                passport_issued=r[fm["PASSPORT_ISSUED"]],
                passport_date_begin=format_date(r[fm["PASSPORT_DATE_BEGIN"]]) if r[fm["PASSPORT_DATE_BEGIN"]] else None,
                passport_date_end=format_date(r[fm["PASSPORT_DATE_END"]]) if r[fm["PASSPORT_DATE_END"]] else None,
            )
    finally:
        try:
            cursor.close()
        finally:
            conn.close()


def _resolve_fk_maps(rows: Sequence[EmpRow]) -> Tuple[Dict[int, int], Dict[str, int]]:
    post_ids = {r.post_id for r in rows if r.post_id is not None}
    local_codes = {r.local_code for r in rows if r.local_code}
    pos_map = dict(
        Position.objects.filter(iabs_post_id__in=post_ids).
        values_list("iabs_post_id", "id")) if post_ids else {}
    comp_map = dict(
        Company.objects.filter(local_code__in=local_codes).
        values_list("local_code", "id")) if local_codes else {}
    return pos_map, comp_map


def _build_user_for_create(r: EmpRow, pos_id_by_post: Dict[int, int],
                           company_id_by_local: Dict[str, int],
                           username: Optional[str]) -> "User":
    return User(
        table_number=r.tab_num,
        last_name=r.last_name,
        first_name=r.first_name,
        father_name=r.middle_name,
        birth_date=r.birth_date,
        status_id=get_condition_id(r.condition),
        position_id=pos_id_by_post.get(r.post_id),
        company_id=company_id_by_local.get(r.local_code),
        begin_work_date=r.date_begin,
        pinfl=r.inps,
        tin=r.inn,
        iabs_staffing_id=r.staffing_id,
        iabs_emp_id=r.emp_id,
        gender=r.gender,
        phone=r.phone,
        passport_seria=r.passport_seria,
        passport_number=r.passport_number,
        passport_issued_by=r.passport_issued,
        passport_issue_date=r.passport_date_begin,
        passport_expiry_date=r.passport_date_end,
        username=username,
    )


def _apply_updates(u: "User", r: EmpRow, pos_id_by_post: Dict[int, int],
                   company_id_by_local: Dict[str, int]) -> None:
    u.table_number = r.tab_num
    u.last_name = r.last_name
    u.first_name = r.first_name
    u.father_name = r.middle_name
    u.birth_date = r.birth_date
    u.status_id = get_condition_id(r.condition)
    u.position_id = pos_id_by_post.get(r.post_id)
    u.company_id = company_id_by_local.get(r.local_code)
    u.begin_work_date = r.date_begin
    u.pinfl = r.inps
    u.tin = r.inn
    u.iabs_staffing_id = r.staffing_id
    u.username = r.phone  # keep original behavior: username mirrors phone on update
    u.phone = r.phone
    u.passport_seria = r.passport_seria
    u.passport_number = r.passport_number
    u.passport_issued_by = r.passport_issued
    u.passport_issue_date = r.passport_date_begin
    u.passport_expiry_date = r.passport_date_end


@shared_task
def update_or_create_users():
    """
    Import or create users from IABS (Oracle) efficiently:
    - Streams Oracle rows in chunks (constant memory)
    - Preloads related Position/Company/User mappings per chunk (no per-row queries)
    - Bulk creates/updates users with safe fallbacks
    """

    created = updated = failed = processed = 0
    chunk: List[EmpRow] = []
    try:
        for r in _stream_oracle_rows():
            chunk.append(r)
            if len(chunk) >= ORACLE_FETCH_CHUNK:
                c, u, f = _flush_chunk(chunk)
                created += c
                updated += u
                failed += f
                processed += len(chunk)
                chunk.clear()
        if chunk:
            c, u, f = _flush_chunk(chunk)
            created += c
            updated += u
            failed += f
            processed += len(chunk)
    except Exception as e:
        logging.error("IABS import failed: %s", e, exc_info=True)
        return f"IABS import failed: {e}"

    msg = f"Users import: processed={processed}, created={created}, updated={updated}, failed={failed}"
    logging.info(msg)
    return msg


def _flush_chunk(rows: Sequence[EmpRow]) -> Tuple[int, int, int]:
    """
    Stage → map FKs → build creates/updates → bulk write.
    Returns (created, updated, failed) for this chunk.
    """
    if not rows:
        return (0, 0, 0)

    pos_map, comp_map = _resolve_fk_maps(rows)
    emp_ids = {r.emp_id for r in rows}
    users_by_emp = existing_users_by_emp(emp_ids, 'active')

    phones = {r.phone for r in rows if r.phone}
    used_usernames = existing_usernames(phones)

    to_create: List[User] = []
    to_update: List[User] = []

    for r in rows:
        try:
            if r.emp_id in users_by_emp:
                u = users_by_emp[r.emp_id]
                _apply_updates(u, r, pos_map, comp_map)
                to_update.append(u)
            else:
                base = r.phone or f"user_{r.emp_id}"
                username = _unique_username(base, used_usernames, fallback=f"user_{r.emp_id}")
                to_create.append(_build_user_for_create(r, pos_map, comp_map, username))
        except Exception as build_err:
            logging.error("Build user failed (emp_id=%s): %s", r.emp_id, build_err, exc_info=True)
            return (0, 0, 1)

    created = _bulk_create_safe(to_create)
    updated = _bulk_update_safe(to_update, fields=[
        "table_number", "last_name", "first_name", "father_name", "birth_date",
        "status_id", "position_id", "company_id", "begin_work_date", "pinfl",
        "tin", "iabs_staffing_id", "username", "phone",
        "passport_seria", "passport_number", "passport_issued_by",
        "passport_issue_date", "passport_expiry_date",
    ])
    return (created, updated, 0)


def _bulk_create_safe(objs: List["User"]) -> int:
    if not objs:
        return 0
    total = 0
    for i in range(0, len(objs), BULK_CREATE_CHUNK):
        part = objs[i:i + BULK_CREATE_CHUNK]
        try:
            with transaction.atomic():
                User.objects.bulk_create(part, batch_size=BULK_CREATE_CHUNK)
            total += len(part)
        except IntegrityError as e:
            # Isolate bad rows without killing the batch
            logging.warning("bulk_create IntegrityError: %s → falling back row-wise", e)
            for o in part:
                try:
                    with transaction.atomic():
                        o.save()
                    total += 1
                except IntegrityError as ee:
                    logging.error("Create failed (emp_id=%s): %s", getattr(o, "iabs_emp_id", None), ee)
    return total


def _bulk_update_safe(objs: List["User"], fields: List[str]) -> int:
    if not objs:
        return 0
    total = 0
    for i in range(0, len(objs), BULK_UPDATE_CHUNK):
        part = objs[i:i + BULK_UPDATE_CHUNK]
        try:
            with transaction.atomic():
                User.objects.bulk_update(part, fields, batch_size=BULK_UPDATE_CHUNK)
            total += len(part)
        except IntegrityError as e:
            logging.warning("bulk_update IntegrityError: %s → falling back row-wise", e)
            for o in part:
                try:
                    with transaction.atomic():
                        User.objects.filter(pk=o.pk).update(**{f: getattr(o, f) for f in fields})
                    total += 1
                except IntegrityError as ee:
                    logging.error("Update failed (emp_id=%s user_id=%s): %s", getattr(o, "iabs_emp_id", None), o.pk, ee)
    return total


@shared_task
def update_usernames():
    """
    Update usernames from IABS database.
    """

    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except IntegrityError as e:
        logging.error(f'Error connecting to Oracle database {e}')
        return f'Error connecting to Oracle database {e}'

    updated_user_count = 0
    failed_user_count = 0

    status_ids = user_search_status_ids()
    users = User.objects.filter(status_id__in=status_ids)

    for user in users:
        sql = "select he.emp_id, he.phone_mobil from ibs.hr_emps_v he where he.emp_id :=1 and he.Condition not in ('P', 'PF', 'PO', 'KP', 'KO')"
        cursor.execute(sql, (user.iabs_emp_id,))
        cur = cursor.fetchone()
        field_map = db_column_name(cursor)

        try:
            phone_number = cur[field_map['PHONE_MOBIL']]
            user.username = phone_number
            user.phone = phone_number
            user.save()
            updated_user_count += 1
        except (IntegrityError, User.DoesNotExist):
            failed_user_count += 1
            continue

    cursor.close()
    conn.close()

    logging.info(f"updated user count {updated_user_count}")
    logging.info(f"failed user count {failed_user_count}")


def update_employee_department(emp_id=None):
    success_count = 0
    fail_count = 0
    multiple_users = []

    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except IntegrityError as e:
        logging.error(f'Error connecting to Oracle database {e}')
        return f'Error connecting to Oracle database {e}'

    if emp_id:
        sql = "select he.Emp_Id, he.Staffing_Id, he.Department_Code, he.Dep_Parent_Code from ibs.hr_emps_v he where he.Condition not in ('P', 'PF', 'PO', 'KP', 'KO') and he.Emp_Id = :1"
        cursor.execute(sql, (emp_id,))
    else:
        sql = "select he.Emp_Id, he.Staffing_Id, he.Department_Code, he.Dep_Parent_Code from ibs.hr_emps_v he where he.Condition not in ('P', 'PF', 'PO', 'KP', 'KO')"
        cursor.execute(sql)

    rows = cursor.fetchall()
    field_map = db_column_name(cursor)
    status_ids = user_search_status_ids()

    if rows:
        for row in rows:
            emp_id = row[field_map['EMP_ID']]
            department_code = row[field_map['DEPARTMENT_CODE']]

            try:
                user = User.objects.get(iabs_emp_id=emp_id, status_id__in=status_ids)
                top_level_dept_id, sub_sub_dept_id = get_dept_ids(department_code, user.company_id)
                user.department_id = sub_sub_dept_id
                user.top_level_department_id = top_level_dept_id
                user.save()
                success_count += 1
            except User.MultipleObjectsReturned:
                multiple_users.append(emp_id)
                fail_count += 1

            except User.DoesNotExist:
                fail_count += 1

    cursor.close()
    conn.close()

    logging.info(f"success count {success_count}")
    logging.info(f"fail count {fail_count}")
    logging.info(f"multiple users {multiple_users}")


@shared_task
def update_employees_department():
    """
    Update employees' department/top-level department from Oracle.
    - Iterates users in batches to bound memory and reduce DB round-trips.
    - For each batch, performs a single bulk UPDATE with CASE expressions.
    - Continues on per-row errors; logs a final summary.
    """
    success_count = 0
    fail_count = 0
    BATCH_SIZE = 500

    # Get sql query
    try:
        sql = _get_oracle_sql('department_codesql')
    except Exception as e:
        sql = "select he.Emp_Id, he.Staffing_Id, he.Department_Code, he.Dep_Parent_Code from ibs.hr_emps_v he where he.Condition not in ('P', 'PF', 'PO', 'KP', 'KO') and he.Emp_Id = :1"

    # 1) Prepare the user stream (only the fields we need)
    status_ids = user_search_status_ids()
    qs = (
        User.objects
        .filter(status_id__in=status_ids)
        .values_list('id', 'iabs_emp_id', 'company_id')
        .order_by('id')
    )

    # 2) Open Oracle connection/cursor with context manager
    with ExitStack() as stack:
        try:
            conn = stack.enter_context(oracle_connection())
            cursor = stack.enter_context(conn.cursor())
        except IntegrityError as e:
            logging.error(f'Error connecting to Oracle database {e}')
            return f'Error connecting to Oracle database {e}'

        field_map_cache: Dict[str, int] = {}
        batch: List[Tuple[int, str, int]] = []

        for pk, emp_id, company_id in qs.iterator(chunk_size=BATCH_SIZE):
            batch.append((pk, emp_id, company_id))
            if len(batch) >= BATCH_SIZE:
                s, f = _process_emp_dept_batch(cursor, sql, field_map_cache, batch)
                success_count += s
                fail_count += f
                batch.clear()

        # Flush any remaining users in the last batch
        if batch:
            s, f = _process_emp_dept_batch(cursor, sql, field_map_cache, batch)
            success_count += s
            fail_count += f
            batch.clear()

    logging.info("update_employees_department finished: success=%d, fail=%d", success_count, fail_count)
    return f"Departments updated: success={success_count}, fail={fail_count}"


@shared_task
def update_user_condition():
    """
    Sync user.status_id (and deactivate resigned users) from Oracle.
    - Streams users to keep memory flat
    - Fetches latest condition per emp_id
    - Uses QuerySet.update() for a single write per user
    """

    status_ids = user_search_status_ids()
    qs = (
        User.objects
        .filter(status_id__in=status_ids)
        .values_list("pk", "iabs_emp_id", "pinfl", "phone", "username")
        .order_by("pk")
    )

    # Get sql query
    try:
        sql = _get_oracle_sql('employee_conditionsql')
    except Exception:
        sql = "Select distinct(he.emp_id), condition, work_now, condition_name, last_update_date From ibs.hr_emps_v he, ibs.hr_emp_works hw where he.emp_id = hw.emp_id and he.emp_id = :1 order by last_update_date desc"

    BATCH_SIZE = 1000
    resigned = 0
    fail = 0

    with ExitStack() as stack:
        try:
            conn = stack.enter_context(oracle_connection())
            cursor = stack.enter_context(conn.cursor())
        except IntegrityError as e:
            logging.error(f'Error connecting to Oracle database {e}')
            return f'Error connecting to Oracle database {e}'

        # Cache of column name → index in the Oracle result set
        field_map_cache: Dict[str, int] = {}
        batch: List[Tuple] = []

        for pk, emp_id, pinfl, phone, username in qs.iterator(chunk_size=BATCH_SIZE):
            batch.append((pk, emp_id, pinfl, phone, username))
            if len(batch) >= BATCH_SIZE:
                s, f = _process_user_condition_batch(cursor, sql, field_map_cache, batch)
                resigned += s
                fail += f
                batch.clear()

        # Flush any remaining users in the last batch
        if batch:
            s, f = _process_user_condition_batch(cursor, sql, field_map_cache, batch)
            resigned += s
            fail += f
            batch.clear()

    logging.info("update_user_condition finished: resigned=%d, fail=%d", resigned, fail)
    return f"Users resigned: {resigned}, fail={fail}"


@shared_task
def replace_chars_with_letter():
    dept_count = 0
    position_count = 0
    company_count = 0
    user_count = 0

    for dept in Department.objects.all():
        dept_count = update_and_count(dept, 'name', dept_count)
        dept.name_uz = dept.name
        dept.name_ru = dept.name
        dept.save()

    time.sleep(2)
    for position in Position.objects.all():
        position_count = update_and_count(position, 'name', position_count)
        position.name_uz = position.name
        position.name_ru = position.name
        position.save()

    time.sleep(2)
    for company in Company.objects.all():
        company_count = update_and_count(company, 'name', company_count)
        company.name_uz = company.name
        company.name_ru = company.name
        company.save()

    user_fields = ['first_name', 'last_name', 'father_name']
    for user in User.objects.all():
        for field in user_fields:
            user_count = update_and_count(user, field, user_count)


def get_users_with_birthdays(lang='uz', force_refresh=False):
    cache_key = f'birthday_users:{lang}'

    # Check if cache needs to be refreshed
    if force_refresh:
        cache.delete(cache_key)

    # Try to fetch from cache
    birthday_cache = cache.get(cache_key)
    if birthday_cache:
        return birthday_cache

    today = datetime.today().date()
    tomorrow = today + timedelta(days=1)

    status_ids = user_search_status_ids()

    # Query users with birthdays today and tomorrow
    birthday_users = User.objects.filter(
        status_id__in=status_ids
    ).filter(
        Q(birth_date__month=today.month, birth_date__day=today.day) |
        Q(birth_date__month=tomorrow.month, birth_date__day=tomorrow.day)
    ).filter(show_birth_date=True)
    serializer = UserSearchSerializer(birthday_users, many=True)
    users_json = serializer.data

    # Cache the users with birthdays for 10 hours
    cache.set(cache_key, users_json, 36000)

    return users_json


@shared_task
def update_users_from_ldap():
    # Define your AD server and credentials
    server_address = os.getenv('LDAP_HOST')  # e.g., 'ldap://yourdomain.com'
    username = os.getenv('LDAP_LOGIN')  # e.g., 'CN=Administrator,CN=Users,DC=example,DC=com'
    password = os.getenv('LDAP_PASSWORD')

    # Create a connection to the server
    server = Server(server_address, get_info=ALL)
    conn = Connection(server, user=username, password=password, auto_bind=True)

    # Define the OU DN and search filter to find all users in the OU
    ou_dn = 'OU=....REPUBLIC,DC=sqb,DC=uz'  # Replace with the distinguished name of your OU
    search_filter = '(objectClass=user)'  # Filter to find user objects
    search_scope = SUBTREE

    # Set page size
    page_size = 1000
    total_entries = 4000
    retrieved_entries = 0
    entries = []

    try:
        conn.search(ou_dn, search_filter, search_scope,
                    attributes=['cn', 'sAMAccountName', 'mail', 'pager', 'telephoneNumber'],
                    paged_size=page_size)
    except LDAPError as e:
        logging.error(f"LDAP search failed: {e}")
        return
    count = 0
    while True:
        for entry in conn.entries:
            entries.append(entry)
            # print(f"CN: {entry.cn.value if entry.cn else None}")
            # print(f"sAMAccountName: {entry.sAMAccountName.value if entry.sAMAccountName else None}")
            # print(f"mail: {entry.mail.value if entry.mail else None}")
            # print(f"pager: {entry.pager.value if entry.pager else None}")
            # print(f"telephoneNumber: {entry.telephoneNumber.value if entry.telephoneNumber else None}")
            # print('-' * 40)
            # count += 1

            retrieved_entries += 1
            if retrieved_entries >= total_entries:
                break

        if retrieved_entries >= total_entries or not conn.result['controls']['1.2.840.113556.1.4.319']['value'][
            'cookie']:
            break

        # Fetch the next page of results
        conn.search(ou_dn, search_filter, search_scope,
                    attributes=['cn', 'sAMAccountName', 'mail', 'pager', 'telephoneNumber'],
                    paged_size=page_size,
                    paged_cookie=conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'])

    for entry in entries:
        pinfl = entry.pager.value

        if pinfl is not None:
            user = User.objects.filter(pinfl=str(pinfl)).first()
            if user:
                user.ldap_login = normalize_login(str(entry.mail.value))
                user.email = str(entry.mail.value)
                user.cisco = normalize_phone(str(entry.telephoneNumber.value))
                user.normalized_cisco = str(entry.telephoneNumber.value)
                user.save()
                count += 1
                # print(count)

    # Unbind the connection
    conn.unbind()


VACATION_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
SICK_LEAVE_QUERY = "SELECT He.emp_id,ht.Name, ht.Staj_All,ht.Staj_Current_Bank,ht.Coefficient, ht.date_begin, ht.date_end from ibs.hr_emps he, ibs.hr_emp_med_lists_v ht WHERE he.condition=:1 and ht.emp_id=he.emp_id and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
ACADEMIC_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
MILITARY_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
UNPAID_LEAVE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
MATERNITY_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
LONG_MATERNITY_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
EDUCATIONAL_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
MATERNITY_AND_SICK_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and TO_CHAR(SYSDATE, 'MM/DD/YYYY') BETWEEN ht.date_begin and ht.date_end"
TRIP_QUERY = "SELECT He.emp_id,ht.date_begin, ht.date_end, ht.Trip_Address, ht.Trip_Reason from ibs.hr_emps he, ibs.hr_emp_trips_v ht WHERE he.condition=:1 and ht.emp_id=he.emp_id and sysdate BETWEEN ht.date_begin and ht.date_end"

# LEAVE QUERIES WITH START AND END DATE
VACATION_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
SICK_LEAVE_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.Name, ht.Staj_All,ht.Staj_Current_Bank,ht.Coefficient, ht.date_begin, ht.date_end from ibs.hr_emps he, ibs.hr_emp_med_lists_v ht WHERE he.condition=:1 and ht.emp_id=he.emp_id and ht.Date_End+1 between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
ACADEMIC_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
MILITARY_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
UNPAID_LEAVE_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
MATERNITY_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
LONG_MATERNITY_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
EDUCATIONAL_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"
MATERNITY_AND_SICK_DATE_RANGE_QUERY = "SELECT He.emp_id,ht.date_begin,ht.date_end from ibs.hr_emps he, ibs.hr_emp_vacation_v ht WHERE ht.emp_id=he.emp_id and he.condition=:1 and ht.Date_End between to_date(:2,'DD.MM.YYYY') AND to_date(:3,'DD.MM.YYYY')"

LEAVE_TYPE_HANDLERS = {
    'OT': (VACATION_QUERY, parse_vacation_row),
    'B': (SICK_LEAVE_QUERY, parse_sick_leave_row),
    'AO': (ACADEMIC_QUERY, parse_vacation_row),
    'I': (MILITARY_QUERY, parse_vacation_row),
    'OB': (UNPAID_LEAVE_QUERY, parse_vacation_row),
    'OD': (MATERNITY_QUERY, parse_vacation_row),
    'OF': (LONG_MATERNITY_QUERY, parse_vacation_row),
    'OU': (EDUCATIONAL_QUERY, parse_vacation_row),
    'DB': (MATERNITY_AND_SICK_QUERY, parse_vacation_row),
    'K': (TRIP_QUERY, parse_trip_row),
}

LEAVE_TYPE_DATE_RANGE_HANDLERS = {
    'OT': (VACATION_DATE_RANGE_QUERY, parse_vacation_row),
    'B': (SICK_LEAVE_DATE_RANGE_QUERY, parse_sick_leave_row),
    'AO': (ACADEMIC_DATE_RANGE_QUERY, parse_vacation_row),
    'I': (MILITARY_DATE_RANGE_QUERY, parse_vacation_row),
    'OB': (UNPAID_LEAVE_DATE_RANGE_QUERY, parse_vacation_row),
    'OD': (MATERNITY_DATE_RANGE_QUERY, parse_vacation_row),
    'OF': (LONG_MATERNITY_DATE_RANGE_QUERY, parse_vacation_row),
    'OU': (EDUCATIONAL_DATE_RANGE_QUERY, parse_vacation_row),
    'DB': (MATERNITY_AND_SICK_DATE_RANGE_QUERY, parse_vacation_row),
}


def attach_user_data(rows, parser_func):
    # Extract all emp_ids
    emp_ids = [row[0] for row in rows]
    users = User.objects.filter(iabs_emp_id__in=emp_ids).select_related(
        'company', 'top_level_department', 'position'
    )
    user_map = {user.iabs_emp_id: user for user in users}

    result = []
    for row in rows:
        base_data = parser_func(row)
        emp_id = base_data['emp_id']
        user = user_map.get(emp_id)
        if not user:
            continue
        base_data.update({
            'full_name': user.full_name,
            'company': user.company.name if user.company else None,
            'department': user.top_level_department.name if user.top_level_department else None,
            'position': user.position.name if user.position else None,
            'tabel_number': user.table_number,
            'color': user.color,
        })
        result.append(base_data)
    return result


def fetch_oracle_users(code: str, start_date=None, end_date=None):
    try:
        conn = oracle_connection()
        cursor = conn.cursor()
    except IntegrityError as e:
        return f'Error connecting to Oracle database {e}'

    if start_date and end_date:
        query_handler = LEAVE_TYPE_DATE_RANGE_HANDLERS.get(code)
        query, parser_func = query_handler if query_handler else (None, None)
    else:
        query_handler = LEAVE_TYPE_HANDLERS.get(code)
        query, parser_func = query_handler if query_handler else (None, None)

    if not query or not parser_func:
        return []

    try:
        cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'MM/DD/YYYY'")
        if start_date and end_date:
            cursor.execute(query, (code, start_date, end_date))
        else:
            cursor.execute(query, (code,))
        rows = cursor.fetchall()
        return attach_user_data(rows, parser_func)
    finally:
        cursor.close()
        conn.close()


@shared_task
def update_employee_rank() -> str:
    """
    Update employee ranks from Oracle to Django.

    - Loads the SQL once
    - Iterates users in chunks to limit memory
    - Queries Oracle per user (keeps SQL unchanged)
    - Collects updates and performs a bulk CASE/WHEN update per chunk
    - Robust logging; no early returns on individual failures
    """
    started = datetime.utcnow()
    status_ids = user_search_status_ids()
    QUERY_NAME = 'emp_rank'
    BATCH_SIZE = 500  # Number of users to process in each batch

    # Preload just what we need: pk + external key
    qs = (
        User.objects
        .filter(status_id__in=status_ids)
        .values_list("pk", "iabs_emp_id")
        .order_by("pk")
    )

    try:
        sql = _get_oracle_sql(QUERY_NAME)
    except Exception:
        return "[ERROR] Could not load emp_rank SQL."

    updated_total = 0
    not_found_total = 0
    errors_total = 0

    # Use ExitStack to ensure both cursor and connection are closed
    with ExitStack() as stack:
        try:
            conn = stack.enter_context(oracle_connection())  # works if oracle_connection() supports __enter__
            cursor = stack.enter_context(conn.cursor())
        except Exception as e:
            logging.error("[ERROR] Failed to connect to Oracle: %s", e)
            return f"[ERROR] Failed to connect to Oracle: {e}"

        field_map_cache: Dict[str, int] = {}

        # Chunked iteration over Users
        batch: List[Tuple[int, str]] = []
        for pk, emp_id in qs.iterator(chunk_size=BATCH_SIZE):
            batch.append((pk, emp_id))
            if len(batch) >= BATCH_SIZE:
                u, nf, err = _process_emp_rank_batch(cursor, sql, field_map_cache, batch)
                updated_total += u
                not_found_total += nf
                errors_total += err
                batch.clear()

        # flush remainder
        if batch:
            u, nf, err = _process_emp_rank_batch(cursor, sql, field_map_cache, batch)
            updated_total += u
            not_found_total += nf
            errors_total += err

    elapsed = (datetime.utcnow() - started).total_seconds()
    logging.info(
        "Employee rank sync finished: updated=%d not_found=%d errors=%d in %.2fs",
        updated_total, not_found_total, errors_total, elapsed
    )
    return f"{updated_total} records successfully updated. Not found: {not_found_total}. Errors: {errors_total}."
