from datetime import date, timedelta
from typing import Iterable
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hr.models import YearModel, IABSCalendar


def iter_days(year: int) -> Iterable[date]:
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        yield d
        d += timedelta(days=1)


class Command(BaseCommand):
    help = "Seed IABSCalendar for a year or year range. Weekends -> work_day=0; weekdays -> 1."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Single year, e.g. 2025")
        parser.add_argument("--start", type=int, help="Start year for a range, e.g. 2025")
        parser.add_argument("--end", type=int, help="End year for a range, e.g. 2027")
        parser.add_argument("--replace", action="store_true",
                            help="Delete existing rows for the year(s) before inserting.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Validate and show counts without writing.")

    def handle(self, *args, **opts):
        year = opts.get("year")
        start = opts.get("start")
        end = opts.get("end")
        replace = opts.get("replace")
        dry_run = opts.get("dry_run")

        # Resolve target years
        if year and (start or end):
            raise CommandError("Use either --year or --start/--end, not both.")
        if start and not end:
            end = start
        if end and not start:
            start = end
        if not year and not (start and end):
            raise CommandError("Provide --year or --start/--end.")

        years = [year] if year else list(range(start, end + 1))

        for y in years:
            if y < 1900 or y > 9999:
                raise CommandError(f"Invalid year: {y}")

        total_created = 0
        total_existing = 0

        for y in years:
            year_obj, _ = YearModel.objects.get_or_create(year=y)

            # Build rows
            rows = []
            for d in iter_days(y):
                weekday = d.weekday()  # Mon=0 ... Sun=6
                is_weekend = weekday in (5, 6)
                rows.append(
                    IABSCalendar(
                        year=year_obj,
                        date=d,
                        work_day=0 if is_weekend else 1,
                        is_holiday=False,
                        holiday_name="",
                        holiday_name_ru="",
                    )
                )

            if dry_run:
                existing = IABSCalendar.objects.filter(year=year_obj).count()
                self.stdout.write(f"[DRY] {y}: existing={existing}, to_insert={len(rows)}")
                total_existing += existing
                continue

            with transaction.atomic():
                if replace:
                    IABSCalendar.objects.filter(year=year_obj).delete()
                    created = len(
                        IABSCalendar.objects.bulk_create(rows, batch_size=1000)
                    )
                else:
                    # Respect your (year, date) UniqueConstraint
                    created = len(
                        IABSCalendar.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)
                    )

            count_now = IABSCalendar.objects.filter(year=year_obj).count()
            self.stdout.write(self.style.SUCCESS(
                f"Seeded {y}: created={created}, total_rows_now={count_now}"
            ))
            total_created += created

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY] Summary: years={years}, total_existing={total_existing}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. Years={years}, total_created={total_created}"
            ))
