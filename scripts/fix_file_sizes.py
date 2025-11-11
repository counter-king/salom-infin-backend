from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from apps.document.models import File

MB_TO_BYTES = Decimal('1000000')  # SI


def _round_bytes(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_HALF_UP))


def run(chunk=2000, dry_run=False):
    """
    Fix rows that were saved as MB but are off by ×1000 (e.g., 28050.46 instead of 28.05).
    """
    qs = (File.objects
          .filter(file_size__gte=1000)  # MB too large → likely ×1000 bug
          .only("id", "file_size", "size"))
    total = qs.count()
    print(f"Candidates: {total}")
    fixed = 0

    with transaction.atomic():
        for f in qs.iterator(chunk_size=chunk):
            old_mb = Decimal(str(f.file_size))
            # divide by 1000 to get intended MB
            new_mb = (old_mb / Decimal('1000')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            new_bytes = _round_bytes(new_mb * MB_TO_BYTES)

            # Optional sanity: if new_mb still ≥ 1024, skip (still looks like GB)
            if new_mb >= Decimal('1024'):
                continue

            if dry_run:
                if fixed < 5:
                    print(f"[DRY] id={f.id} MB {old_mb} -> {new_mb}, bytes -> {new_bytes}")
                fixed += 1
                continue

            f.file_size = float(new_mb)
            f.size = new_bytes
            f.save(update_fields=["file_size", "size"])
            fixed += 1

        if dry_run:
            transaction.set_rollback(True)

    print(f"Fixed: {fixed} / {total}")
