import uuid

from django.conf import settings
from django.db import models

from base_model.models import BaseModel

LANGUAGE_CHOICES = [("uz", "Uzbek"), ("ru", "Russian")]


class NotificationTemplate(BaseModel):
    key = models.CharField(max_length=64)  # e.g., "late_notice"
    lang = models.CharField(max_length=2)  # "uz"/"ru"
    content = models.TextField()  # plain text, not HTML
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.key}:{self.lang}"

    class Meta:
        unique_together = ("key", "lang")


class TelegramPairRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name="telegram_pair_requests")
    request_token = models.TextField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    telegram_phone = models.CharField(max_length=20, null=True, blank=True)
    telegram_id = models.BigIntegerField(null=True, blank=True)
    telegram_username = models.CharField(max_length=255, null=True, blank=True)
    confirmation_code = models.CharField(max_length=10, null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.id}:{self.telegram_id}"

    def is_expired(self, now):
        return now >= self.expires_at


class TelegramProfile(BaseModel):
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="uz")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    chat_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)  # set False on 403

    def __str__(self):
        return f"{self.user_id}:{self.chat_id}"


class TelegramNotificationLog(BaseModel):
    # idempotency key: template + user + hashed context window or explicit key
    key = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    chat_id = models.BigIntegerField()
    template = models.CharField(max_length=64)
    payload = models.JSONField()  # rendered message + meta
    status = models.CharField(max_length=16, default="pending")  # pending/sent/failed
    error = models.TextField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key}:{self.chat_id}"

    class Meta:
        indexes = [models.Index(fields=["user", "template"])]
