import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Tuple, Set

from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.hr.models import (
    AttendanceException,
    DailySummary,
    PayrollCell,
    PayrollPeriod,
    PayrollRow,
)
from apps.reference.models import ExceptionEmployee
from .calendar import is_working_day, choose_mid_pay_date, choose_final_pay_date

EIGHT_HOURS = Decimal("8.00")
ZERO_HOURS = Decimal("0.00")


def get_excluded_employees() -> Set[int]:
    key = "payroll:excluded_employees:v1"
    cached = cache.get(key)
    if cached is not None:
        return set(cached)  # cached as list

    today = timezone.localdate()
    ids = list(
        ExceptionEmployee.objects.filter(is_active=True)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today))
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today))
        .values_list("user_id", flat=True)
    )

    cache.set(key, ids, timeout=5 * 3600)  # store list
    return set(ids)


def _nearest_whole_hour(seconds: int) -> int:
    # nearest integer hours, cap at 8
    if not seconds or seconds <= 0:
        return 0
    hours = int((seconds + 1800) // 3600)  # nearest hour
    return min(hours, 8)


def _ensure_period_for(company_id: int, dept_id: int, y: int, m: int, type: str) -> PayrollPeriod:
    # Optional: set mid/final anchors for reports
    mid = choose_mid_pay_date(y, m)
    fin = choose_final_pay_date(y, m)
    defaults = {"mid_pay_date": mid, "final_pay_date": fin, "type": type}
    if type == 'department':
        period, _ = PayrollPeriod.objects.get_or_create(
            company_id=company_id,
            department_id=dept_id, year=y, month=m,
            defaults=defaults
        )
    else:
        period, _ = PayrollPeriod.objects.get_or_create(
            company_id=company_id,
            department_id=None, year=y, month=m,
            defaults=defaults
        )
    # keep anchors fresh if calendar changed
    if period.mid_pay_date != mid or period.final_pay_date != fin:
        period.mid_pay_date, period.final_pay_date = mid, fin
        period.save(update_fields=["mid_pay_date", "final_pay_date", "modified_date"])
    return period


def _approval_sets(user_ids: list[int], target_date) -> Tuple[Set[int], Set[int]]:
    """
    Returns:
      approved_exc_uids: users with an APPROVED attendance exception on target_date
      approved_expl_uids: users with an APPROVED explanation letter on target_date
    Notes:
      - Adjust the Q() parts for exact fields.
      - We purposely keep them separate to match a decision tree.
    """
    base = AttendanceException.objects.filter(
        employee_id__in=set(user_ids),
        attendance__date=target_date,
    )

    # 1) Exception approved
    approved_exc_uids = set(
        base.filter(status="approved")
        .values_list("employee_id", flat=True)
        .distinct()
    )

    # 2) Explanation letter approved (examples of common field names shown)
    expl_q = Q(explanation_letter__is_signed=True)
    approved_expl_uids = set(
        base.filter(expl_q)
        .values_list("employee_id", flat=True)
        .distinct()
    )

    return approved_exc_uids, approved_expl_uids


def upsert_cells_for_date(target_date: dt.date, *, actor_user=None) -> dict:
    """
    Build/refresh payroll cells for ALL companies for a single date.
    Returns brief stats.
    """
    is_work = is_working_day(target_date)

    ds_rows = list(
        DailySummary.objects
        .select_related("user", "user__company", "user__top_level_department", "user_status")
        .filter(date=target_date)
        .values(
            "user_id", "user__company_id", "date", "worked_seconds",
            "present", "absent", "late_minutes", "early_leave_minutes",
            "user_status__code", "user__top_level_department_id", "user__company__is_main"
        )
    )
    if not ds_rows:
        return {"date": str(target_date), "updated_cells": 0, "skipped_frozen": 0}

    # Group by company for period isolation
    by_company: Dict[(int, int, int), list] = defaultdict(list)
    for r in ds_rows:
        key = (r["user__company_id"], r["user__company__is_main"], r["user__top_level_department_id"])
        by_company[key].append(r)

    updated_cells = 0
    skipped_frozen = 0
    excluded_employees = get_excluded_employees()

    with transaction.atomic():
        for (company_id, is_main, dept_id), rows in by_company.items():
            y, m = target_date.year, target_date.month
            # Optionally lock this period to avoid concurrent writers
            if is_main:
                period = _ensure_period_for(company_id, dept_id, y, m, "department")
            else:
                period = _ensure_period_for(company_id, dept_id, y, m, "branch")

            window = "mid" if target_date <= period.mid_pay_date else "final"
            # skip only if the window holding target_date is locked
            if (window == "mid" and period.mid_locked) or (window == "final" and period.final_locked):
                skipped_frozen += len(rows)
                continue

            user_ids = [r["user_id"] for r in rows]

            # 1) Ensure PayrollRow exists for each user (bulk create)
            existing_rows = {
                rr.employee_id: rr
                for rr in PayrollRow.objects.filter(period=period, employee_id__in=user_ids)
            }
            to_create = []
            for r in rows:
                uid = r["user_id"]
                if uid not in existing_rows:
                    to_create.append(PayrollRow(
                        period=period,
                        employee_id=uid,
                        department_id=r.get("user__top_level_department_id") or None
                    ))
            if to_create:
                PayrollRow.objects.bulk_create(to_create, ignore_conflicts=True)
                # refresh dict
                existing_rows.update({
                    rr.employee_id: rr
                    for rr in PayrollRow.objects.filter(period=period, employee_id__in=user_ids)
                })

            # 2) Precompute exceptions once
            approved_exc_uids, approved_expl_uids = _approval_sets(user_ids, target_date)

            # 3) Build all cells in memory, then bulk upsert
            cells_to_upsert = []
            for r in rows:
                uid = r["user_id"]
                row = existing_rows[uid]

                worked_seconds = int(r.get("worked_seconds") or 0)
                present = bool(r.get("present"))
                late = int(r.get("late_minutes") or 0)
                early = int(r.get("early_leave_minutes") or 0)
                status_code = (r.get("user_status__code") or "").strip()

                # Decide cell (logic unchanged, just flattened)
                if not is_work:
                    code, hours, kind = "", ZERO_HOURS, "off"
                else:
                    if uid in excluded_employees:
                        # Excluded employee → full 8 hours always
                        code, hours, kind = "8", EIGHT_HOURS, "work"
                    elif status_code != "A":
                        if status_code == "K":
                            code, hours, kind = "8", EIGHT_HOURS, "trip"
                        elif status_code == "B":
                            code, hours, kind = "0", ZERO_HOURS, "sick"
                        elif status_code == "OT":
                            code, hours, kind = "0", ZERO_HOURS, "vacation"
                        else:
                            code, hours, kind = status_code, ZERO_HOURS, "absent"
                    elif present and late == 0 and early == 0:
                        code, hours, kind = "8", EIGHT_HOURS, "work"
                    elif uid in approved_exc_uids:
                        # Rule 1: exception approved => full 8
                        code, hours, kind = "8", EIGHT_HOURS, "work"
                    elif uid in approved_expl_uids:
                        # Rule 2: explanation letter approved => nearest hour from worked_seconds
                        ii = _nearest_whole_hour(worked_seconds)
                        code = "8" if ii >= 8 else str(ii)
                        hours = EIGHT_HOURS if ii >= 8 else Decimal(f"{ii}.00")
                        kind = "work" if ii > 0 else "absent"
                    else:
                        # Rule 3: neither approved => zero
                        code, hours, kind = "0", ZERO_HOURS, "absent"

                cells_to_upsert.append(
                    PayrollCell(row=row, date=target_date, code=code, hours=hours, kind=kind)
                )

            if cells_to_upsert:
                # PostgreSQL / Django ≥ 4.1
                PayrollCell.objects.bulk_create(
                    cells_to_upsert,
                    update_conflicts=True,
                    unique_fields=["row", "date"],
                    update_fields=["code", "hours", "kind"],
                )
                updated_cells += len(cells_to_upsert)

            # 4) Recompute quick totals per row in ONE query, then bulk update
            agg = (
                PayrollCell.objects
                .filter(row__period=period)
                .values("row_id")
                .annotate(
                    th=Sum("hours"),
                    abs_cnt=Count("id", filter=Q(kind="absent")),
                    vac_cnt=Count("id", filter=Q(kind="vacation")),
                    sick_cnt=Count("id", filter=Q(kind="sick")),
                    trip_cnt=Count("id", filter=Q(kind="trip")),
                )
            )
            # Map row_id -> totals
            totals_by_row = {
                a["row_id"]: (
                    a["th"] or ZERO_HOURS,
                    a["abs_cnt"] or 0,
                    a["trip_cnt"] or 0,
                    a["vac_cnt"] or 0,
                    a["sick_cnt"] or 0,
                )
                for a in agg
            }

            rows_to_update = []
            for rr in existing_rows.values():
                th, ab, tr, va, si = totals_by_row.get(rr.id, (ZERO_HOURS, 0, 0, 0, 0))
                if (
                        rr.total_hours != th or
                        rr.total_absent != ab or
                        rr.total_trip != tr or
                        rr.total_vacation != va or
                        rr.total_sick != si
                ):
                    rr.total_hours = th
                    rr.total_absent = ab
                    rr.total_trip = tr
                    rr.total_vacation = va
                    rr.total_sick = si
                    rows_to_update.append(rr)

            if rows_to_update:
                PayrollRow.objects.bulk_update(
                    rows_to_update,
                    ["total_hours", "total_absent", "total_trip", "total_vacation", "total_sick"]
                )

            # Update employee_count on the period (distinct employees in this scope)
            emp_count = PayrollRow.objects.filter(period=period).count()
            if period.employee_count != emp_count:
                period.employee_count = emp_count
                period.save(update_fields=["employee_count", "modified_date"])

    return {"date": str(target_date), "updated_cells": updated_cells, "skipped_frozen": skipped_frozen}

# def upsert_cells_for_date(target_date: dt.date, *, actor_user=None) -> dict:
#     """
#     Build/refresh payroll cells for ALL companies for a single date.
#     Returns brief stats.
#     """
#     is_work = is_working_day(target_date)
#
#     # Pull DailySummary rows for the date across all companies
#     ds_qs = (
#         DailySummary.objects
#         .select_related("user", "user__company", "user_status")
#         .filter(date=target_date)
#         .values(
#             "user_id", "user__company_id", "date", "worked_seconds",
#             "present", "absent", "late_minutes", "early_leave_minutes",
#             "user_status__code", "user__top_level_department"
#         )
#     )
#
#     if not ds_qs:
#         return {"date": str(target_date), "updated_cells": 0, "skipped_frozen": 0}
#
#     by_company = defaultdict(list)
#     for r in ds_qs:
#         by_company[r["user__company_id"]].append(r)
#
#     updated_cells = 0
#     skipped_frozen = 0
#
#     with transaction.atomic():
#         for company_id, rows in by_company.items():
#             y, m = target_date.year, target_date.month
#
#             # Optionally lock this period to avoid concurrent writers
#             period = _ensure_period_for(company_id, y, m, actor_user)
#
#             # Skip writes if period is frozen/approved
#             if period.status in ("approved", "frozen"):
#                 skipped_frozen += len(rows)
#                 continue
#
#             user_ids = [r["user_id"] for r in rows]
#
#             # cache of rows for this period
#             existing_rows = {
#                 rr.employee_id: rr
#                 for rr in PayrollRow.objects.filter(period=period)
#             }
#
#             to_create = []
#             for r in rows:
#                 uid = r["user_id"]
#
#                 row = existing_rows.get(uid)
#                 if row is None:
#                     row = PayrollRow.objects.create(
#                         period=period,
#                         employee_id=uid,
#                         department_id=r.get("user__top_level_department") or None
#                     )
#                     existing_rows[uid] = row
#
#                 worked_seconds = int(r.get("worked_seconds") or 0)
#                 present = bool(r.get("present"))
#                 absent = bool(r.get("absent"))
#                 late = int(r.get("late_minutes") or 0)
#                 early = int(r.get("early_leave_minutes") or 0)
#                 status_code = (r.get("user_status__code") or "").strip()
#
#                 # Decide cell
#                 if not is_work:
#                     # Non-working day → blank by default
#                     code = ""
#                     hours = Decimal("0.00")
#                     kind = "off"
#                 else:
#                     # Working day
#                     if status_code != "A":
#                         if status_code == "K":
#                             code = "8"
#                             hours = EIGHT_HOURS
#                             kind = "trip"
#                         else:
#                             # Client-ready code straight from DailySummary.user_status.code
#                             code = status_code
#                             hours = Decimal("0.00")
#                             kind = "status"
#                     elif present and late == 0 and early == 0:
#                         code = "8"
#                         hours = EIGHT_HOURS
#                         kind = "work"
#                     elif has_approved_exception(uid, target_date):
#                         ii = _nearest_whole_hour(worked_seconds)
#                         code = "8" if ii >= 8 else str(ii)
#                         hours = EIGHT_HOURS if ii >= 8 else Decimal(f"{ii}.00")
#                         kind = "work" if ii > 0 else "absent"
#                     else:
#                         code = "0"
#                         hours = Decimal("0.00")
#                         kind = "absent"
#
#                 # Upsert the cell for that date
#                 obj, created = PayrollCell.objects.update_or_create(
#                     row=row, date=target_date,
#                     defaults={"code": code, "hours": hours, "kind": kind}
#                 )
#                 updated_cells += 1
#
#                 # Recompute row quick totals (cheap, per-row)
#                 agg = row.cells.aggregate(
#                     th=Sum("hours"),
#                     abs_cnt=Count("id", filter=Q(kind="absent"))
#                 )
#                 row.total_hours = agg["th"] or Decimal("0.00")
#                 row.total_absent = agg["abs_cnt"] or 0
#                 row.save(update_fields=["total_hours", "total_absent"])
#
#     return {"date": str(target_date), "updated_cells": updated_cells, "skipped_frozen": skipped_frozen}
