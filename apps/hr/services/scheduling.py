from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.db import transaction

from apps.hr.models import EmployeeSchedule, WorkSchedule
from apps.user.models import User

BULK_CHUNK = 500


@dataclass(frozen=True)
class BulkAssignResult:
    schedule_id: int
    updated_default_count: int  # number of employees now pointing to this as default
    created_rows: int  # how many rows created (didn't exist before)
    switched_from_other: int  # how many had a row but switched default
    skipped_missing_employees: List[int]


def _chunks(seq: List[int], size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


@transaction.atomic
def bulk_assign_default_schedule(
        *,
        schedule_id: int,
        employee_ids: Iterable[int],
        assigned_by_id: Optional[int] = None,
        notes: str = "",
) -> BulkAssignResult:
    """
    For each employee:
      - Unset any existing default row
      - Set (or create) the row for schedule_id as default=True
    """
    employee_ids = list(dict.fromkeys(int(e) for e in employee_ids if e is not None))
    if not employee_ids:
        return BulkAssignResult(schedule_id, 0, 0, 0, [])

    schedule = WorkSchedule.objects.only("id").filter(id=schedule_id).first()
    if not schedule:
        raise ValueError(f"Schedule {schedule_id} does not exist")

    existing_emps = set(User.objects.filter(id__in=employee_ids).values_list("id", flat=True))
    missing_emps = [e for e in employee_ids if e not in existing_emps]
    target_emps = [e for e in employee_ids if e in existing_emps]

    updated_default = 0
    created_rows = 0
    switched_from_other = 0

    for chunk in _chunks(target_emps, BULK_CHUNK):
        # Lock this employee's rows to avoid races
        emp_rows = (
            EmployeeSchedule.objects
            .select_for_update()
            .filter(employee_id__in=chunk)
        )

        # Map: employee -> list of rows
        rows_by_emp = {}
        for row in emp_rows.only("id", "employee_id", "schedule_id", "is_default", "notes"):
            rows_by_emp.setdefault(row.employee_id, []).append(row)

        # We will collect updates and creates
        to_update = []
        to_create = []

        for eid in chunk:
            rows = rows_by_emp.get(eid, [])
            had_any_default = any(r.is_default for r in rows)

            # Unset any default rows
            for r in rows:
                if r.is_default:
                    r.is_default = False
                    to_update.append(r)

            # Find or create the row for this schedule
            target_row = next((r for r in rows if r.schedule_id == schedule_id), None)
            if target_row:
                if not target_row.is_default:
                    target_row.is_default = True
                    # Merge notes if provided
                    if notes:
                        target_row.notes = (target_row.notes + "\n" if target_row.notes else "") + notes
                    if assigned_by_id is not None:
                        target_row.modified_by_id = assigned_by_id
                    to_update.append(target_row)
                    switched_from_other += 1 if had_any_default else 0
                    updated_default += 1
                else:
                    # already default on this schedule (rare, due to earlier unset)
                    updated_default += 1
            else:
                to_create.append(
                    EmployeeSchedule(
                        employee_id=eid,
                        schedule_id=schedule_id,
                        is_default=True,
                        modified_by_id=assigned_by_id,
                        notes=notes or "",
                    )
                )
                created_rows += 1
                updated_default += 1

        if to_update:
            EmployeeSchedule.objects.bulk_update(
                to_update, ["is_default", "modified_by", "notes", "modified_date"]
            )
        if to_create:
            EmployeeSchedule.objects.bulk_create(to_create, batch_size=BULK_CHUNK)

    return BulkAssignResult(
        schedule_id=schedule_id,
        updated_default_count=updated_default,
        created_rows=created_rows,
        switched_from_other=switched_from_other,
        skipped_missing_employees=missing_emps,
    )
