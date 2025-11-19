from apps.docflow.models import Reviewer, Assignee
from apps.docflow.models import InboxItem


# def fanout_to_review(document_id):
#     """Draft root resolution exists: reviewers (and assistants) get 'to_review'."""
#     reviewer_ids = set(Reviewer.objects.filter(document_id=document_id).values_list("user_id", flat=True))
#     items = []
#     for rid in reviewer_ids:
#         items.append(InboxItem(user_id=rid, document_id=document_id, kind="to_review"))
#     if items:
#         InboxItem.objects.bulk_create(items, update_conflicts=True)


def sync_fanout_to_review(instance):
    """
    Ensure inbox(to_review) exactly matches current reviewers (+ assistants).
    """
    document_id = instance.document_id
    target = set(Reviewer.objects.filter(document_id=document_id).values_list("user_id", flat=True))

    existing_qs = InboxItem.objects.filter(document_id=document_id, kind="to_review")
    existing = set(existing_qs.values_list("user_id", flat=True))

    to_add = target - existing
    to_del = existing - target

    if to_add:
        InboxItem.objects.bulk_create(
            [InboxItem(user_id=uid, document_id=document_id,
                       review_id=instance.id, kind="to_review") for uid in to_add],
            ignore_conflicts=True,  # safe with uniq constraint
        )

    if to_del:
        existing_qs.filter(user_id__in=to_del).delete()


def sync_fanout_to_assignee(instance):
    """
    Ensure inbox(to_execute) exactly matches current assignees
    """
    document = instance.assignment.reviewer.document

    target = set(Assignee.objects.filter(assignment_id=instance.assignment_id).values_list("user_id", flat=True))

    existing_qs = InboxItem.objects.filter(document=document, kind="to_execute")
    existing = set(existing_qs.values_list("user_id", flat=True))

    to_add = target - existing
    to_del = existing - target

    if to_add:
        InboxItem.objects.bulk_create(
            [InboxItem(user_id=uid,
                       document_id=document.id,
                       assignment_id=instance.assignment_id,
                       kind="to_execute") for uid in to_add],
            ignore_conflicts=True
        )

    if to_del:
        existing_qs.filter(user_id__in=to_del).delete()
