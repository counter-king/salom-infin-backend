from django.db import transaction
from django.utils.timezone import localdate
from apps.docflow.models import RegCounter


def allocate_reg_number(*, journal, reg_date) -> tuple[str, int, int]:
    """
    Returns (reg_no, reg_year, reg_order)
    Atomically increments per-(journal, year) counter.
    """
    year = reg_date.year
    yy = year % 100

    with transaction.atomic():
        # lock this journal+year row; create if absent
        counter, created = (RegCounter.objects
                            .select_for_update()
                            .get_or_create(journal=journal, year=year, defaults={"next_no": 1}))
        order = counter.next_no
        counter.next_no = order + 1
        counter.save(update_fields=["next_no"])

    reg_no = f"{journal.index}-{yy}/{order}"
    return reg_no, year, order
