import logging
from datetime import date
from typing import Dict, Tuple, List, Optional

from django.db import transaction
from django.db.models import When, Value, Case, F, FloatField, DateField
from django.db.models.functions import Cast
from django.utils import timezone

from apps.user.models import User
from apps.user.services import (
    get_dept_ids,
    get_condition_id,
    format_date,
    make_inactive_signers,
    existing_users_by_emp,
)
from utils.constant_ids import user_search_status_ids
from utils.db_connection import db_column_name
from utils.utils import to_float


def _process_emp_dept_batch(
        cursor,
        sql: str,
        field_map_cache: Dict[str, int],
        batch: List[Tuple[int, str, int]],
) -> Tuple[int, int]:
    """
    For a batch of (user_pk, emp_id, company_id):
      - query Oracle for each emp_id,
      - resolve department IDs via get_dept_ids,
      - bulk update all changed users in a single UPDATE.
    Returns (success_count, fail_count).
    """
    updates: Dict[int, Tuple[int, int]] = {}  # pk -> (department_id, top_level_department_id)
    success = 0
    fail = 0

    for pk, emp_id, company_id in batch:
        try:
            cursor.execute(sql, (emp_id,))
            row = cursor.fetchone()
            if not row:
                logging.warning("No rows found for emp_id=%s (user_id=%s)", emp_id, pk)
                continue

            # Build field map once from the executed cursor
            if not field_map_cache:
                # Example: {"EMP_ID": 0, "STAFFING_ID": 1, "DEPARTMENT_CODE": 2, "DEP_PARENT_CODE": 3}
                field_map_cache.update(db_column_name(cursor))

            dept_idx = field_map_cache.get("DEPARTMENT_CODE")
            if dept_idx is None:
                logging.error("'DEPARTMENT_CODE' column not found in Oracle result (emp_id=%s, user_id=%s)", emp_id, pk)
                fail += 1
                continue

            department_code = row[dept_idx]

            # Map external department_code -> (top_level_dept_id, sub_sub_dept_id) in our Django DB
            top_level_dept_id, sub_sub_dept_id = get_dept_ids(department_code, company_id)
            updates[pk] = (sub_sub_dept_id, top_level_dept_id)
            success += 1

        except Exception as e:
            logging.error("Oracle lookup failed for emp_id=%s (user_id=%s): %s", emp_id, pk, e, exc_info=True)
            fail += 1

    if updates:
        # Build CASE expressions for both target columns
        dept_whens = [When(pk=pk, then=Value(dept_id)) for pk, (dept_id, _top) in updates.items()]
        top_whens = [When(pk=pk, then=Value(top_id)) for pk, (_dept, top_id) in updates.items()]
        # Introspect the real DB type behind your FKs
        dept_fk = User._meta.get_field("department")  # models.ForeignKey(...)
        dept_output_field = dept_fk.target_field.__class__()  # e.g., BigAutoField() → bigint

        top_fk = User._meta.get_field("top_level_department")
        top_output_field = top_fk.target_field.__class__()  # match its PK type

        # Single atomic bulk update per batch
        with transaction.atomic():
            User.objects.filter(pk__in=updates.keys()).update(
                department_id=Case(
                    *dept_whens,
                    default=F("department_id"),
                    output_field=dept_output_field
                ),
                top_level_department_id=Case(
                    *top_whens,
                    default=F("top_level_department_id"),
                    output_field=top_output_field
                ),
            )

        logging.info("Batch updated %d users' departments.", len(updates))

    return success, fail


def _fetch_rank_for_emp(
        cursor, sql: str, emp_id: str, field_map_cache: Dict[str, int]
) -> Optional[str]:
    """
    Execute the rank query for a single employee and return the CODE (rank) or None.
    Caches the cursor column name→index map after first successful execute.
    """
    cursor.execute(sql, (emp_id,))
    row = cursor.fetchone()
    if not row:
        return None

    if not field_map_cache:
        # build once from cursor description of the executed statement
        field_map_cache.update(db_column_name(cursor))  # e.g., {"CODE": 0, ...}

    code_idx = field_map_cache.get("CODE")
    if code_idx is None:
        logging.error("[ERROR] 'CODE' column not found in result set for emp_id=%s", emp_id)
        return None

    return row[code_idx]


def _process_emp_rank_batch(
        cursor, sql: str, field_map_cache: Dict[str, int], batch: List[Tuple[int, str]]
) -> Tuple[int, int, int]:
    """
    For a batch of (user_pk, emp_id), query Oracle and apply a single bulk update.
    Returns (updated_count, not_found_count, errors_count).
    """
    rank_by_user_pk: Dict[int, float] = {}
    not_found = 0
    errors = 0

    for pk, emp_id in batch:
        try:
            rank = _fetch_rank_for_emp(cursor, sql, emp_id, field_map_cache)
            rank_f = to_float(rank)
            if rank_f is None:
                logging.warning("[WARN] No numeric rank for emp_id=%s (user_id=%s) raw=%r", emp_id, pk, rank)
                not_found += 1
                continue
            rank_by_user_pk[pk] = rank_f
        except Exception as e:
            logging.error("[ERROR] Oracle query failed for emp_id=%s (user_id=%s): %s", emp_id, pk, e)
            errors += 1

    updated = 0
    if rank_by_user_pk:
        # ensure every THEN expression is typed as float
        whens = [
            When(pk=pk, then=Cast(Value(val), FloatField()))
            for pk, val in rank_by_user_pk.items()
        ]
        with transaction.atomic():
            updated = (
                User.objects
                .filter(pk__in=rank_by_user_pk.keys())
                .update(
                    rank=Case(
                        *whens,
                        # keep type as float on the default branch too
                        default=F("rank"),
                        output_field=FloatField(),
                    )
                )
            )
        logging.info("Batch updated %d user ranks.", updated)

    return updated, not_found, errors


def _suffix(value: Optional[str], ts: int) -> Optional[str]:
    """Append ' at {ts}' to a non-empty string; keep None as None."""
    if not value:
        return value
    return f"{value} at {ts}"


def _process_user_condition_batch(
        cursor, sql: str, field_map_cache: Dict[str, int], batch: List[Tuple]
) -> Tuple[int, int]:
    """
    For a batch of (user_pk, emp_id), query Oracle and apply a single bulk update.
    Returns (updated_count, not_found_count, errors_count).
    """
    success = 0
    fail = 0
    # Status codes that mean the employee has resigned / is not active
    RESIGNED_CODES = {'P', 'PF', 'PO', 'KP', 'KO'}
    ts = int(timezone.now().timestamp())

    for pk, emp_id, pinfl, phone, username in batch:
        try:
            cursor.execute(sql, (emp_id,))
            row = cursor.fetchone()
            if not row:
                logging.warning("No rows found for emp_id=%s (user_id=%s)", emp_id, pk)
                fail += 1
                continue

            # Build field map once from the executed cursor
            if not field_map_cache:
                # Example: {"EMP_ID": 0, "STAFFING_ID": 1, "DEPARTMENT_CODE": 2, "DEP_PARENT_CODE": 3}
                field_map_cache.update(db_column_name(cursor))

            cond_idx = field_map_cache.get('CONDITION')
            last_idx = field_map_cache.get('LAST_UPDATE_DATE')
            if cond_idx is None or last_idx is None:
                logging.error("Expected columns missing in Oracle result (user_id=%s, emp_id=%s)", pk, emp_id)
                fail += 1
                continue

            cond_code = row[cond_idx]
            last_update = row[last_idx]

            # Map condition code to status_id
            new_status_id = get_condition_id(cond_code)
            if new_status_id is None:
                logging.warning("Unknown condition code %r for emp_id=%s (user_id=%s)", cond_code, emp_id, pk)
                fail += 1
                continue
            # Prepare fields to update
            update_fields = {'status_id': new_status_id}
            if cond_code in RESIGNED_CODES:
                update_fields.update({
                    'is_user_active': False,
                    'is_active': False,
                    'pinfl': (f'P{pinfl}' if pinfl and not str(pinfl).startswith('P') else pinfl),
                    'phone': _suffix(phone, ts),
                    'username': _suffix(username, ts),
                    'end_date': format_date(last_update) if last_update else None,
                })

            # One DB write per user
            with transaction.atomic():
                User.objects.filter(pk=pk).update(**update_fields)
                if cond_code in RESIGNED_CODES:
                    make_inactive_signers(pk)
                    success += 1
        except Exception as e:
            logging.error("Oracle lookup failed for emp_id=%s (user_id=%s): %s", emp_id, pk, e, exc_info=True)
            fail += 1

    return success, fail


def _update_user_leave_end_date(emp_to_end: Dict[int, date], today: date) -> (int, int):
    """
    For a batch of emp_id -> end_date, update User.leave_end_date using a single
    CASE/WHEN update (by iabs_emp_id). Returns (updated_count, missing_users_count).
    """
    if not emp_to_end:
        return (0, 0)

    status_ids = user_search_status_ids()

    # Fetch existing users for these emp_ids
    users_by_emp = existing_users_by_emp(
        set(emp_to_end.keys()),
        mode="status",
        status_ids=status_ids
    )

    missing = len(emp_to_end) - len(users_by_emp)
    if not users_by_emp:
        return (0, missing)

    # Build CASE arms on iabs_emp_id → specific date
    whens: List[When] = [
        When(iabs_emp_id=emp_id, then=Value(end_date))
        for emp_id, end_date in emp_to_end.items()
        if emp_id in users_by_emp
    ]

    with transaction.atomic():
        # Single bulk update statement
        updated = User.objects.filter(
            iabs_emp_id__in=users_by_emp.keys()
        ).update(
            leave_end_date=Case(
                *whens,
                default=F("leave_end_date"),
                output_field=DateField(),
            )
        )

    logging.info("Batch update: users=%d updated=%d missing=%d", len(users_by_emp), updated, missing)
    return (updated, missing)
