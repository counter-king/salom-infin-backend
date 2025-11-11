import calendar
import datetime as dt

from apps.hr.models import IABSCalendar


def is_working_day(date: dt.date) -> bool:
    cal = (
        IABSCalendar.objects
        .filter(date=date)
        .values_list("work_day", flat=True)
        .first()
    )
    # If not found, be conservative: treat as non-working OR default to Mon-Fri.
    if cal is None:
        return date.weekday() < 5
    return bool(cal)


def choose_mid_pay_date(year: int, month: int) -> dt.date:
    for d in (16, 15, 14, 13):
        day = dt.date(year, month, d)
        if is_working_day(day):
            return day
    # fallback if 13..16 all off
    d = 12
    while d >= 1:
        day = dt.date(year, month, d)
        if is_working_day(day):
            return day
        d -= 1
    raise RuntimeError("No working day for mid pay")


def last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def choose_final_pay_date(year: int, month: int) -> dt.date:
    last = last_day_of_month(year, month)
    for d in range(last, 26, -1):  # last..27
        day = dt.date(year, month, d)
        if is_working_day(day):
            return day
    for d in range(26, 0, -1):
        day = dt.date(year, month, d)
        if is_working_day(day):
            return day
    raise RuntimeError("No working day for final pay")
