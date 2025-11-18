from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.docflow.models import Reviewer, Assignee
from apps.docflow.services.fan_out import sync_fanout_to_review, sync_fanout_to_assignee


@receiver([post_save, post_delete], sender=Reviewer)
def _sync_inbox_on_reviewer_change(sender, instance, **kwargs):
    sync_fanout_to_review(instance)


@receiver([post_save, post_delete], sender=Assignee)
def _sync_inbox_on_assignee_change(sender, instance, **kwargs):
    sync_fanout_to_assignee(instance)
