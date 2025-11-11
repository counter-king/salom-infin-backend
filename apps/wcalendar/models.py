from django.db import models

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class CalendarModel(BaseModel):
    title = models.CharField(max_length=255, null=True)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    organizer = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    attachments = models.ManyToManyField("document.File", blank=True)
    priority = models.ForeignKey("reference.Priority", on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(null=True, blank=True, max_length=15, choices=CONSTANTS.CALENDAR_TYPES.CHOICES)
    source = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=CONSTANTS.CALENDAR_MEETING_SOURCE.CHOICES)
    link = models.CharField(max_length=255, null=True, blank=True)
    notify_by = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=CONSTANTS.NOTIFY_BY.CHOICES)
    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=CONSTANTS.CALENDAR_STATUS.CHOICES,
        default=CONSTANTS.CALENDAR_STATUS.DEFAULT
    )

    def __str__(self):
        return '{}'.format(self.title)


class CalendarParticipant(BaseModel):
    calendar = models.ForeignKey(CalendarModel, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    is_informed = models.BooleanField(default=False)
    is_accepted = models.BooleanField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.user.full_name)
