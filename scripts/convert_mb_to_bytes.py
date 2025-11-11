from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db import transaction
from apps.document.models import File  # adjust import if your app label/path differs

# Constants
MIB_TO_MB = Decimal('1.048576')  # 1 MiB = 1.048576 MB (SI)
MB_TO_BYTES = Decimal('1000000')  # 1 MB (SI) = 1,000,000 bytes


def _quantize_2_dp(x: Decimal) -> Decimal:
    return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _round_to_int(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_HALF_UP))


def run(chunk=2000, dry_run=False, lower_id=None, upper_id=None):
    """
    Fix legacy File.file_size that was saved as MiB but labeled MB:
      - Correct file_size to true MB (× 1.048576, 2 decimals).
      - Set size (bytes) = MB × 1,000,000 (rounded to nearest byte).
    Only processes rows where size IS NULL (idempotent).

    Args:
        chunk (int): queryset iterator chunk size
        dry_run (bool): if True, don't write changes; just count
        lower_id (int|None): optional inclusive lower bound on File.id
        upper_id (int|None): optional inclusive upper bound on File.id
    Returns:
        dict summary
    """
    qs = File.objects.filter(file_size__isnull=False).only("id", "file_size")
    if lower_id is not None:
        qs = qs.filter(id__gte=lower_id)
    if upper_id is not None:
        qs = qs.filter(id__lte=upper_id)

    total = qs.count()
    print(f"Rows to process (size IS NULL): {total}")
    converted = 0
    failed = 0

    with transaction.atomic():
        for obj in qs.iterator(chunk_size=chunk):
            try:
                # file_size currently holds a number computed as bytes/(1024**2) -> MiB.
                # Correct it to MB (SI) by multiplying by 1.048576, keep 2 decimals.
                mib = Decimal(str(obj.file_size))
                if mib < 0:
                    # normalize negatives defensively
                    mib = Decimal('0')

                mb_corrected = _quantize_2_dp(mib * MIB_TO_MB)  # MB with 2 decimals
                bytes_val = _round_to_int(mb_corrected * MB_TO_BYTES)

                if dry_run:
                    converted += 1
                    # show a couple of samples for confidence
                    if converted <= 5:
                        print(f"[DRY] id={obj.id}  MiB(stored)={mib}  MB(fixed)={mb_corrected}  bytes={bytes_val}")
                    continue

                # Persist both the corrected MB and the bytes
                obj.file_size = float(mb_corrected)  # keep as 2-decimal float in MB (SI)
                obj.size = bytes_val  # exact bytes (BigIntegerField)
                obj.save(update_fields=["file_size", "size"])
                converted += 1

            except (InvalidOperation, ValueError) as e:
                failed += 1
                if converted < 5:  # print a few diagnostics
                    print(f"[SKIP] id={obj.id} file_size={obj.file_size} error={e}")

        if dry_run:
            transaction.set_rollback(True)

    summary = {"total": total, "converted": converted, "failed": failed, "dry_run": dry_run}
    print(f"Done. Converted: {converted}, Failed: {failed}, Total: {total}, Dry-run: {dry_run}")
    print(summary)
