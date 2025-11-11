import datetime
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.hr.models import YearModel, IABSCalendar
from utils.db_connection import oracle_connection
from utils.utils import fmt_d


@shared_task
def sync_iabs_calendar():
    """
    Syncs ONLY work_day from IABS for the next 30 days.
    Does NOT touch is_holiday or holiday_name (they are maintained manually).
    """
    conn = None
    cursor = None

    try:
        conn = oracle_connection()
        cursor = conn.cursor()
        cursor.arraysize = 2000

        today = timezone.localdate()
        end_date = today + datetime.timedelta(days=30)
        p_start = fmt_d(today)
        p_end = fmt_d(end_date)

        # Read only what we need, and DISTINCT to avoid dup source rows
        sql = (
            "SELECT DISTINCT t.oper_day, t.day_status "
            "FROM ibs.calendar t "
            "WHERE t.oper_day BETWEEN to_date(:1, 'dd.mm.yyyy') AND to_date(:2, 'dd.mm.yyyy')"
        )
        cursor.execute(sql, (p_start, p_end))

        year_obj, _ = YearModel.objects.get_or_create(year=today.year)

        # Existing rows by date (keep this minimal: we only compare work_day)
        existing_qs = (
            IABSCalendar.objects
            .filter(year=year_obj, date__range=(today, end_date))
            .only("id", "date", "work_day")
        )
        existing_by_date = {obj.date: obj for obj in existing_qs}

        to_create = []
        to_update = []
        seen_new_dates = set()

        while True:
            batch = cursor.fetchmany(2000)
            if not batch:
                break

            for oper_day, day_status in batch:
                # Normalize Oracle datetime -> date
                d = oper_day.date() if hasattr(oper_day, "date") else oper_day

                if d < today or d > end_date:
                    continue

                # Update existing: ONLY work_day
                if d in existing_by_date:
                    obj = existing_by_date[d]
                    if obj.work_day != day_status:
                        obj.work_day = day_status
                        to_update.append(obj)
                    continue

                # New row (dedupe inside this run)
                if d in seen_new_dates:
                    continue
                seen_new_dates.add(d)

                to_create.append(
                    IABSCalendar(
                        year=year_obj,
                        date=d,
                        work_day=day_status
                    )
                )

        created = 0
        updated = 0

        # Single atomic write
        with transaction.atomic():
            if to_create:
                # Safe with UNIQUE(year, date); avoids duplicates in races
                IABSCalendar.objects.bulk_create(to_create, ignore_conflicts=True)
                created = len(to_create)

            if to_update:
                # Update ONLY work_day; holidays remain untouched
                IABSCalendar.objects.bulk_update(to_update, ["work_day"])
                updated = len(to_update)

        msg = f"OK bulk synced {created} created, {updated} updated between {p_start} and {p_end}"
        logging.info(msg)
        return msg

    except Exception as e:
        logging.exception("sync_iabs_calendar failed")
        return f"ERR {e}"

    finally:
        cursor.close()
        conn.close()
