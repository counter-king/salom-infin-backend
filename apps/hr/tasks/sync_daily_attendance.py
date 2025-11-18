import datetime as dt
import logging
import time
from typing import Dict, Optional, List, Iterable, Any, Tuple

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.models import IngestState
from apps.hr.models import DailySummary
from apps.hr.services.hik_time_fmt import vendor_day_bounds_str
from apps.hr.views.v1.attendance import FaceIdClient
from apps.user.models import User
from config.celery import app
from utils.constant_ids import user_reasonable_status_ids
from utils.exception import SourceUnavailableError
from utils.tools import check_if_workday, send_sms_to_phone
from utils.utils import as_int, to_utc
from utils.constants import CONSTANTS

# If vendor duration fields are MINUTES, keep this True. If they are SECONDS, set False.
REPORT_DURATIONS_ARE_MINUTES = False

# Cache keys / TTL
_FACE_MAP_KEY = "faceid:personcode_to_pinfl:v1"
_FACE_MAP_LOCK = "faceid:personcode_to_pinfl:lock"
_FACE_MAP_TTL = 9 * 60 * 60  # 9 hours

# New: remember recent misses so we don't trigger full refresh again and again
_FACE_MISS_PREFIX = "faceid:miss:"
_FACE_MISS_TTL = 60 * 30  # 30 min

# New: track when we last built the map
_FACE_MAP_META = "faceid:personcode_to_pinfl:meta"  # {"ts": epoch, "size": int}
_FACE_MAP_MIN_RETRY_SEC = 600  # 10 minutes: don't refresh again sooner than this

WINDOW_START_HOUR = 12  # 12:00
WINDOW_END_HOUR = 22  # 22:00 (exclusive)

# Cyrillic + Latin variants; case-insensitive
_PINFL_ALIASES = {"пинфл", "pinfl"}


def _to_date(date_str: str) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(date_str)
    except Exception:
        return None


def _minutes(x) -> int:
    v = as_int(x)
    return v if REPORT_DURATIONS_ARE_MINUTES else v // 60


def _extract_pinfl(person: Dict[str, Any]) -> Optional[str]:
    lst = person.get("customFieldList") or []
    for item in lst:
        name = (item.get("customFieldName")
                or item.get("customFiledName")  # vendor typo seen in the wild
                or "").strip().lower()
        val = (item.get("customFieldValue") or "").strip()
        if not name or not val:
            continue
        if name in _PINFL_ALIASES:
            return val
    return None


def build_map_from_people(people_iter: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """Build dict: personCode -> PINFL (skips entries without PINFL/personCode)."""
    m: Dict[str, str] = {}
    for p in people_iter:
        code = str(p.get("personCode") or "").strip()
        if not code:
            continue
        pinfl = _extract_pinfl(p)
        if not pinfl:
            continue
        m[code] = pinfl
    return m


def refresh_people_map(client, *, page_size: int = 500) -> dict[str, str]:
    # prevent very frequent rebuilds
    meta = cache.get(_FACE_MAP_META) or {}
    last_ts = meta.get("ts") or 0
    if time.time() - last_ts < _FACE_MAP_MIN_RETRY_SEC:
        return cache.get(_FACE_MAP_KEY, {})

    lock_ok = cache.add(_FACE_MAP_LOCK, "1", 300)  # 5 min lock
    if not lock_ok:
        return cache.get(_FACE_MAP_KEY, {})

    try:
        m = build_map_from_people(client.iter_people(page_size=page_size))
        cache.set(_FACE_MAP_KEY, m, _FACE_MAP_TTL)
        cache.set(_FACE_MAP_META, {"ts": time.time(), "size": len(m)}, _FACE_MAP_TTL)
        return m
    finally:
        cache.delete(_FACE_MAP_LOCK)


def get_people_map() -> dict[str, str]:
    return cache.get(_FACE_MAP_KEY, {})


def _miss_key(person_code: str) -> str:
    return f"{_FACE_MISS_PREFIX}{person_code}"


def _resolve_user_by_person_code(person_code: str, *, client=None, page_size: int = 500):
    """
    O(1) lookup from cached hashmap.
    - If map empty and client provided -> refresh once.
    - If a specific person_code was recently a miss -> do NOT refresh again.
    """

    pc = str(person_code)

    # recent negative cache?
    if cache.get(_miss_key(pc)) is not None:
        return None

    # try current map
    m = get_people_map()
    pinfl = m.get(pc)

    # only refresh when map is missing/stale — NOT on every miss of a single code
    if not pinfl and client is not None and not m:
        m = refresh_people_map(client, page_size=page_size)
        pinfl = m.get(pc)

    if not pinfl:
        # remember this miss to avoid another rebuild on the next call
        cache.set(_miss_key(pc), 1, _FACE_MISS_TTL)
        return None

    try:
        user = User.objects.get(pinfl=pinfl)

        # if user has no hik_person_code, set it
        if not user.hik_person_code:
            user.hik_person_code = pc
            user.save(update_fields=['hik_person_code'])

        return user
    except User.MultipleObjectsReturned:
        logging.warning(f'Multiple users with PINFL={pinfl} for personCode={pc}')
    except User.DoesNotExist:
        # cache the miss so we don't keep refreshing for this code
        cache.set(_miss_key(pc), 1, _FACE_MISS_TTL)
        return None


def determine_status(
        late_m: int,
        early_leave_m: int,
        begin_utc: Optional[dt.datetime] = None,
        end_utc: Optional[dt.datetime] = None,
        *,
        is_workday: bool,
) -> Tuple[str, str]:
    """
    Returns (check_in_status, check_out_status).
    REASONABLE is never auto-assigned (HR sets it manually).
    """
    in_status = CONSTANTS.ATTENDANCE.CHECK_IN_STATUS
    out_status = CONSTANTS.ATTENDANCE.CHECK_OUT_STATUS

    # --- IN status (arrival)
    if not begin_utc:
        if end_utc:
            check_in_status = in_status.NOT_CHECKED  # has OUT, missing IN
        else:
            check_in_status = in_status.ABSENT if is_workday else in_status.NOT_CHECKED
    elif late_m > 0:
        check_in_status = in_status.WAS_LATE
    else:
        check_in_status = in_status.ON_TIME

    # --- OUT status (departure)
    if not end_utc:
        if begin_utc:
            check_out_status = out_status.NOT_CHECKED  # has IN, missing OUT
        else:
            check_out_status = out_status.ABSENT if is_workday else out_status.NOT_CHECKED
    elif early_leave_m > 0:
        check_out_status = out_status.EARLY_LEAVE
    else:
        check_out_status = out_status.ON_TIME_LEAVE

    return check_in_status, check_out_status


def sync_daily_report(
        begin_time: str | dt.datetime,
        end_time: str | dt.datetime,
        *,
        page_size: int = 200,
        org_index_codes: Optional[List[int]] = None,
        person_code: Optional[str] = None,
        is_workday: bool
) -> Tuple[Dict[str, Any], Dict[str, dict]]:
    """
    Pulls all daily records and upserts DailySummary(user, date).
    """
    client = FaceIdClient()
    upserted = 0
    skipped_no_user = 0
    seen = 0
    users_latency_map: Dict[str, dict[str, int]] = {}
    reasonable_absences = user_reasonable_status_ids()

    for rec in client.iter_report(
            begin_time, end_time, page_size=page_size,
            org_index_codes=org_index_codes, person_code=person_code
    ):
        seen += 1

        # --- Extract fields following your sample ---
        person = (rec.get("personInfo") or {})
        pc = str(person.get("personCode") or "")
        person_id = str(person.get("personID") or "")
        plan_info = (rec.get("planInfo") or {})
        plan_begin_time = to_utc(str(plan_info.get("planBeginTime") or ""))  # plan begin time may be None
        plan_end_time = to_utc(str(plan_info.get("planEndTime") or ""))  # plan end time may be None

        date_val = _to_date(str(rec.get("date") or ""))
        week_day = as_int(rec.get("weekDay"))  # 1=Mon .. 7=Sun
        if date_val is None:
            continue

        base = (rec.get("attendanceBaseInfo") or {})
        begin_utc = to_utc(str(base.get("beginTime") or ""))  # check in time may be None
        end_utc = to_utc(str(base.get("endTime") or ""))  # check out time may be None

        late_m = _minutes((rec.get("lateInfo") or {}).get("durationTime", 0))
        early_m = _minutes((rec.get("earlyInfo") or {}).get("durationTime", 0))
        abs_m = _minutes((rec.get("absenceInfo") or {}).get("durationTime", 0))

        # Worked seconds: prefer explicit begin/end; else fall back to normal/allDurationTime if provided
        if begin_utc and end_utc and end_utc > begin_utc:
            worked_seconds = int((end_utc - begin_utc).total_seconds())
        else:
            # Some vendors report normal or allDurationTime (often in MINUTES)
            normal_m = _minutes((rec.get("normalInfo") or {}).get("durationTime", 0))
            all_m = _minutes(str(rec.get("allDurationTime") or "0"))
            if normal_m == 0 and all_m == 0 and begin_utc:
                now = timezone.now()
                # This seconds is temporary, real worked seconds determined after one day
                worked_seconds = int((now - begin_utc).total_seconds())
            else:
                minutes = normal_m if normal_m > 0 else all_m
                worked_seconds = minutes * 60

        # Re-derive late/early if vendor gave zeros but just in case, we have lateness
        if late_m == 0 and begin_utc and begin_utc > plan_begin_time:
            late_seconds = int((begin_utc - plan_begin_time).total_seconds())
            late_m = _minutes(late_seconds)

        if early_m == 0 and end_utc and end_utc < plan_end_time:
            early_leave_seconds = int((plan_end_time - end_utc).total_seconds())
            early_m = _minutes(early_leave_seconds)

        # Presence/absence flags
        present = bool(worked_seconds > 0 or begin_utc or end_utc)
        abs_m = max(0, abs_m)

        if present:
            absent = False
        else:
            absent = bool(is_workday or abs_m > 0)

        # Determine statuses (REASONABLE never auto-assigned for now)
        check_in_status, check_out_status = determine_status(
            late_m, early_m, begin_utc, end_utc, is_workday=is_workday
        )

        # Resolve user
        user = _resolve_user_by_person_code(pc, client=client)
        if not user:
            skipped_no_user += 1
            continue

        # If user status is reasonable, set status accordingly
        if user.status_id in reasonable_absences:
            check_in_status = CONSTANTS.ATTENDANCE.CHECK_IN_STATUS.REASONABLE
            check_out_status = CONSTANTS.ATTENDANCE.CHECK_OUT_STATUS.REASONABLE

        if late_m > 0 and getattr(user, "phone", None):
            users_latency_map[user.phone] = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'late_minutes': late_m
            }

        # Row-scoped atomic block: one record won't roll back the whole batch
        try:
            with transaction.atomic():
                # Upsert DailySummary (one row per user+date)
                obj, _ = DailySummary.objects.update_or_create(
                    user=user, date=date_val,
                    defaults={
                        "first_check_in": begin_utc,  # may be None
                        "last_check_out": end_utc,  # may be None
                        "worked_seconds": worked_seconds,
                        "late_minutes": late_m,
                        "early_leave_minutes": early_m,
                        "present": present,
                        "absent": absent,
                        'week_day': week_day,
                        "source_agg": "vendor_daily_v1",
                        'person_code': pc,
                        'person_id': person_id,
                        'plan_begin_time': plan_begin_time,
                        'plan_end_time': plan_end_time,
                        'check_in_status': check_in_status,
                        'check_out_status': check_out_status,
                        'user_status': user.status,
                    }
                )
                upserted += 1
        except Exception as e:
            logging.error(f"Upsert failed for user={user.id} date={date_val}: {e}")
            pass

    return {"seen": seen, "upserted": upserted, "skipped_no_user": skipped_no_user}, users_latency_map


def _daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def _run_sync_window(date_obj) -> dict:
    is_workday, meta = check_if_workday(date_obj)
    if not is_workday:
        return {"status": "NO_WORKDAY", "date": str(date_obj), "reason": meta}

    begin_str, end_str = vendor_day_bounds_str(date_obj)
    try:
        data, users_latency_map = sync_daily_report(
            begin_time=begin_str,
            end_time=end_str,
            is_workday=is_workday
        )
    except SourceUnavailableError as e:
        return {"status": "OUTAGE", "date": str(date_obj), "reason": str(e)[:300]}

    seen = int((data or {}).get("seen", 0))
    upserted = int((data or {}).get("upserted", 0))
    return {
        "status": "OK" if (seen or upserted) else "EMPTY",
        "date": str(date_obj),
        "data": data,
        "users_latency_map": len(users_latency_map) if (seen or upserted) else 0
    }


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def sync_attendance_backfill_then_today(self):
    today = timezone.localdate()
    yesterday = today - dt.timedelta(days=1)

    with transaction.atomic():
        state, _ = IngestState.objects.select_for_update().get_or_create(source=IngestState.SOURCE_FACE_ID)
        # Start from the next unprocessed date, or today if first run
        start_date = (state.last_success_date + dt.timedelta(days=1)) if state.last_success_date else today

        # (A) Backfill gap up to yesterday
        if start_date <= yesterday:
            for d in _daterange(start_date, yesterday):
                r = _run_sync_window(d)
                if r["status"] == "OUTAGE":
                    state.mark_outage(r["reason"])
                    return {"phase": "backfill", **r}
                # Advance cursor even on EMPTY/NO_WORKDAY to avoid looping forever
                state.mark_ok(success_date=d)

        # (B) Process today (check-ins usually; we won’t expect checkout yet)
        r_today = _run_sync_window(today)
        if r_today["status"] == "OUTAGE":
            state.mark_outage(r_today["reason"])
            return {"phase": "today", **r_today}
        state.mark_ok(success_date=today)

    # Notify lateness only for today's result (avoid spam on backfill)
    if r_today["status"] == "OK" and r_today.get("users_latency_map"):
        notify_users_about_lateness.apply_async((r_today["users_latency_map"],), countdown=5)

    # (C) Reconcile yesterday *again* to pick late checkouts (safe & idempotent)
    # This runs outside the DB lock and does not change the cursor.
    r_reconcile = _run_sync_window(yesterday)

    return {
        "phase": "done",
        "today": r_today,
        "reconcile_yesterday": r_reconcile
    }


@shared_task
def sync_daily_attendance():
    # today = timezone.localdate()
    # is_workday, data = check_if_workday(today)
    # if not is_workday:
    #     return data
    #
    # begin_date = f'{today}T00:00:00 08:00'
    # end_date = f'{today}T23:59:59 08:00'
    # logging.info(f"Syncing daily attendance for {begin_date} to {end_date}")
    # data, users_latency_map = sync_daily_report(begin_time=begin_date,
    #                                             end_time=end_date,
    #                                             is_workday=is_workday)
    #
    # # Send notifications for late users
    # notify_users_about_lateness.apply_async((users_latency_map,), countdown=5)
    # data["begin_date"] = begin_date
    # data["end_date"] = end_date
    #
    # return data
    return sync_attendance_backfill_then_today.delay().id


def _in_time_window(now):
    """
    Return True if local time is in [12:00, 22:00), else False.
    """

    local = timezone.localtime(now)
    return WINDOW_START_HOUR <= local.hour < WINDOW_END_HOUR


@shared_task
def sync_daily_unregistered_attendance():
    """
    NOTE: Current semantics (by queryset below):
      - Target DailySummary rows for *today* where `first_check_in` is NULL,
        i.e., people who either aren't appearing in FaceID yet or simply haven't checked in.

    Runs every ~2 hours on workdays.
    Steps:
      1) Check workday; bail early if not.
      2) Gather distinct person_codes from DailySummary(date=today, first_check_in__isnull=True).
      3) Call sync_daily_report for each person code (chunked).
      4) Return detailed counts.
    """
    today = timezone.localdate()
    is_workday, data = check_if_workday(today)
    if not is_workday:
        return data

    now = timezone.now()
    if not _in_time_window(now):
        logging.info(
            f"[attendance] Skipping run at {timezone.localtime(now).isoformat()} "
            f"(allowed window {WINDOW_START_HOUR}:00–{WINDOW_END_HOUR}:00)"
        )
        return None  # or return {} if you prefer an empty JSON object

    begin_date = f'{today}T00:00:00 08:00'
    end_date = f'{today}T23:59:59 08:00'
    logging.info(f"Syncing daily attendance for unregistered users for {begin_date} to {end_date}")

    sync_daily_report(begin_time=begin_date, end_time=end_date, is_workday=is_workday)

    return {
        "date": str(today),
        "begin": begin_date,
        "end": end_date,
    }


@app.task(max_retries=1)
def notify_users_about_lateness(users_latency_map: Dict[str, dict[str, int]]):
    # for phone, info in users_latency_map.items():
    #     first_name = info.get('first_name', '')
    #     last_name = info.get('last_name', '')
    #     late_minutes = info.get('late_minutes')
    #     message = f"Hurmatli {first_name} {last_name}, Siz bugun ishga {late_minutes} daqiqa kechikdingiz. Iltimos, sababini SalomCBU tizimida kiriting."
    #     try:
    #         send_sms_to_phone(phone, message)
    #     except Exception as e:
    #         logging.error(f"Failed to send SMS to {phone}: {e}")
    #         return f"Failed to send SMS to {phone}: {e}"

    return f"Sent {len(users_latency_map)} lateness empty notifications."


@shared_task
def sync_yesterday_attendance():
    # yesterday = timezone.localdate() - dt.timedelta(days=1)
    # is_workday, data = check_if_workday(yesterday)
    # if not is_workday:
    #     return data
    #
    # begin_date = f'{yesterday}T00:00:00 08:00'
    # end_date = f'{yesterday}T23:59:59 08:00'
    # logging.info(f"Syncing yesterday's attendance for {begin_date} to {end_date}")
    # data, late_users = sync_daily_report(begin_time=begin_date, end_time=end_date, is_workday=is_workday)
    # return data
    # Ensures backfill+today+reconcile are executed; returns the composite result
    return sync_attendance_backfill_then_today.delay().id
