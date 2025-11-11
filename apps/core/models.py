from django.core.cache import cache
from django.db import models
from django.utils import timezone

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class CacheKey(BaseModel):
    key = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    expires_in = models.IntegerField(default=3600)  # Cache expiration time in seconds (default 1 hour)

    def clear_cache(self):
        """
        Clears the cache for this specific cache key.
        """
        cache.delete(self.key)

    def __str__(self):
        return self.key


class PageRanking(BaseModel):
    page_url = models.CharField(max_length=1000)
    rank = models.IntegerField(default=5)
    comment = models.CharField(null=True, blank=True, max_length=255)

    def __str__(self):
        return '{}'.format(self.rank)


class SQLQuery(BaseModel):
    query_type = models.CharField(max_length=50, unique=True)
    sql_query = models.TextField()
    parameters = models.JSONField(blank=True, null=True)
    required_params = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.query_type

    class Meta:
        verbose_name = 'SQL Query'
        verbose_name_plural = 'SQL Queries'


class DepartmentManager(BaseModel):
    department = models.ForeignKey('company.Department', on_delete=models.SET_NULL, null=True,
                                   related_name='manager_links')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True,
                             related_name='department_manager_links')
    is_primary = models.BooleanField(default=False)  # the main signer/approver for this role
    sort_order = models.PositiveIntegerField(default=0)  # escalation order within same role
    is_active = models.BooleanField(default=True, db_index=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.department)

    class Meta:
        # Prevent duplicate links for the same (department, user, role)
        constraints = [
            models.UniqueConstraint(
                fields=["department", "user"],
                name="uniq_department_user",
            )
        ]
        indexes = [
            models.Index(fields=["department", "is_active"]),
            models.Index(fields=["user"]),
            models.Index(fields=["valid_from"]),
            models.Index(fields=["valid_until"]),
        ]

    @property
    def is_current(self) -> bool:
        from django.utils import timezone
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.valid_from and self.valid_from > today:
            return False
        if self.valid_until and self.valid_until < today:
            return False
        return True


class BranchManager(BaseModel):
    branch = models.ForeignKey("company.Company", on_delete=models.CASCADE, related_name="manager_links")
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL,
                             null=True, blank=True,
                             related_name="branch_manager_links")
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.branch)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["branch", "user"], name="uniq_branch_user")
        ]
        indexes = [models.Index(fields=["branch", "is_active"])]


class IngestState(models.Model):
    """Single moving cursor per source (e.g., 'face_id')."""
    SOURCE_FACE_ID = "face_id"

    source = models.CharField(max_length=50, unique=True, default=SOURCE_FACE_ID)
    last_success_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, default="OK")  # OK | OUTAGE
    outage_started_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    reason = models.TextField(null=True, blank=True)

    def mark_outage(self, outage_reason=None):
        if self.status != "OUTAGE":
            self.status = "OUTAGE"
            self.outage_started_at = timezone.now()
            self.reason = outage_reason
            self.save(update_fields=["status", "outage_started_at", "updated_at", "reason"])

    def mark_ok(self, success_date=None):
        self.status = "OK"
        if success_date:
            self.last_success_date = success_date
        self.save(update_fields=["status", "last_success_date", "updated_at"])
