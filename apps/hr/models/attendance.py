from django.db import models, transaction
from django.db.models import Q, UniqueConstraint

from base_model.models import BaseModel
from utils.constants import CONSTANTS

ATTENDANCE = CONSTANTS.ATTENDANCE


class AttendanceEvent(BaseModel):
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL,
                             related_name='attendance_events', null=True)
    event_type = models.CharField(max_length=50, null=True, blank=True, choices=ATTENDANCE.TYPES.CHOICES)
    event_time = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, null=True, blank=True)
    external_id = models.CharField(max_length=128, unique=True)
    raw_payload = models.JSONField(default=dict)

    def __str__(self):
        return f'AttendanceEvent {self.user} - {self.event_type} - {self.event_time}'

    class Meta:
        verbose_name = 'Attendance Event'
        verbose_name_plural = 'Attendance Events'


class DailySummary(BaseModel):
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL,
                             related_name='attendance_summaries', null=True)
    user_status = models.ForeignKey('user.UserStatus', on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(db_index=True)
    first_check_in = models.DateTimeField(null=True, blank=True)
    last_check_out = models.DateTimeField(null=True, blank=True)
    week_day = models.IntegerField(null=True, blank=True)
    worked_seconds = models.IntegerField(default=0)
    late_minutes = models.IntegerField(default=0)
    early_leave_minutes = models.IntegerField(default=0)
    present = models.BooleanField(default=False)
    absent = models.BooleanField(default=False)
    has_reason = models.BooleanField(default=False)
    source_agg = models.CharField(max_length=16, default='calc_v1')
    person_code = models.CharField(max_length=64, null=True, blank=True)
    person_id = models.CharField(max_length=64, null=True, blank=True)
    plan_begin_time = models.DateTimeField(null=True, blank=True)
    plan_end_time = models.DateTimeField(null=True, blank=True)
    check_in_status = models.CharField(max_length=50, choices=ATTENDANCE.CHECK_IN_STATUS.CHOICES, null=True)
    check_out_status = models.CharField(max_length=50, choices=ATTENDANCE.CHECK_OUT_STATUS.CHOICES, null=True)

    def __str__(self):
        return f'DailySummary {self.user} - {self.date}'

    class Meta:
        verbose_name = 'Daily Summary'
        verbose_name_plural = 'Daily Summaries'


class WorkScheduleQuerySet(models.QuerySet):
    def latest_first(self):
        # deterministic: created_date then id
        return self.order_by('-created_date', '-id')

    def default(self):
        return self.filter(is_default=True)


class WorkScheduleManager(models.Manager):
    def get_queryset(self):
        return WorkScheduleQuerySet(self.model, using=self._db)

    def set_default(self, schedule_id: int) -> None:
        """
        Make the given schedule the sole default, atomically and idempotently.
        """
        # Unset others in a single statement
        self.filter(is_default=True).exclude(pk=schedule_id).update(is_default=False)
        # Set this one (even if it's already default—idempotent)
        self.filter(pk=schedule_id).update(is_default=True)

    def ensure_some_default(self) -> None:
        """
        If no default exists, promote the latest to default.
        Safe to call after create/update/delete.
        """
        if not self.filter(is_default=True).exists():
            latest_id = self.get_queryset().latest_first().values_list('id', flat=True).first()
            if latest_id:
                self.set_default(latest_id)


class WorkSchedule(BaseModel):
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    lunch_start_time = models.TimeField(null=True, blank=True)
    lunch_end_time = models.TimeField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    objects = WorkScheduleManager()

    class Meta:
        # Optional: default ordering so you don't have to repeat it in queries
        ordering = ('-created_date', '-id')
        # PostgreSQL-only: guarantees at most one default
        # constraints = [
        #     models.UniqueConstraint(
        #         condition=Q(is_default=True),
        #         fields=[],  # no columns; condition creates a partial unique index
        #         name="unique_default_work_schedule",
        #     )
        # ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Keep 'default' logic cohesive:
        - Save normally.
        - If this is marked default, unset others atomically.
        - Else ensure at least one default exists.
        """
        super().save(*args, **kwargs)
        if self.is_default:
            # Make sure this is the only default
            type(self).objects.set_default(self.pk)
        else:
            # If there is currently no default, promote one
            type(self).objects.ensure_some_default()


class EmployeeScheduleQuerySet(models.QuerySet):
    def for_employee(self, employee_id):
        return self.filter(employee_id=employee_id)

    def defaults(self):
        return self.filter(is_default=True)


class EmployeeScheduleManager(models.Manager):
    def get_queryset(self):
        return EmployeeScheduleQuerySet(self.model, using=self._db)

    @transaction.atomic
    def set_default(self, *, employee_id: int, schedule_id: int, notes: str = ""):
        # 1) Lock parent employee row to serialize even when there are no assignments yet
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.select_for_update().filter(pk=employee_id).exists()

        # 2) Lock existing assignments for this employee
        qs = self.select_for_update().filter(employee_id=employee_id)

        # 3) Unset any existing defaults
        qs.filter(is_default=True).update(is_default=False)

        # 4) Upsert the (employee, schedule) row
        obj, created = self.get_or_create(
            employee_id=employee_id,
            schedule_id=schedule_id,
            defaults={
                "is_default": True,
                "notes": notes or "",
            },
        )
        if not created:
            changed = False
            if not obj.is_default:
                obj.is_default = True
                changed = True
            if notes:
                obj.notes = (obj.notes + "\n" if obj.notes else "") + notes
                changed = True
            if changed:
                obj.save(update_fields=["is_default", "notes"])
        return obj


class EmployeeSchedule(BaseModel):
    employee = models.ForeignKey('user.User', on_delete=models.CASCADE)
    schedule = models.ForeignKey(WorkSchedule, on_delete=models.PROTECT, related_name='employees_current')
    notes = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    objects = EmployeeScheduleManager()

    def __str__(self):
        return f'{self.employee} - {self.schedule}'

    class Meta:
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["schedule"]),
            models.Index(fields=["employee", "is_default"]),
        ]
        constraints = [
            # Prevent duplicate rows for the same (employee, schedule)
            UniqueConstraint(
                name="uniq_employee_schedule_pair",
                fields=["employee", "schedule"],
            ),
        ]


class HRBranchScope(BaseModel):
    """
    HR user's scope on branches (companies).
    One row = one HR user has access to one branch, optionally with extra flags.
    """
    hr_user = models.ForeignKey(
        'user.User', on_delete=models.CASCADE, related_name="branch_scopes"
    )
    branch = models.ForeignKey(
        "company.Company", on_delete=models.PROTECT, related_name="hr_scopes"
    )
    can_approve = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("hr_user", "branch")]
        indexes = [
            models.Index(fields=["hr_user", "branch"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["hr_user"]),
        ]
        verbose_name = "HR Branch Scope"
        verbose_name_plural = "HR Branch Scopes"

    def __str__(self):
        return f"{self.hr_user} → {self.branch}"


class HRDepartmentScope(BaseModel):
    """
    HR user's scope on departments.
    One row = one HR user has access to one department.
    """
    hr_user = models.ForeignKey(
        'user.User', on_delete=models.CASCADE, related_name="department_scopes"
    )
    department = models.ForeignKey(
        "company.Department", on_delete=models.PROTECT, related_name="hr_scopes"
    )
    can_approve = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("hr_user", "department")]
        indexes = [
            models.Index(fields=["hr_user", "department"]),
            models.Index(fields=["department"]),
            models.Index(fields=["hr_user"]),
        ]
        verbose_name = "HR Department Scope"
        verbose_name_plural = "HR Department Scopes"

    def __str__(self):
        return f"{self.hr_user} → {self.department}"


class AttendanceException(BaseModel):
    employee = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True,
                                 related_name="attendance_exceptions")
    attendance = models.ForeignKey('hr.DailySummary', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="exceptions")
    attachments = models.ManyToManyField('document.File', blank=True)
    kind = models.CharField(max_length=20, choices=ATTENDANCE.EXCEPTION_KIND.CHOICES, null=True)
    reason = models.ForeignKey('reference.AttendanceReason', on_delete=models.PROTECT, related_name="exceptions")
    note = models.TextField(blank=True, default="")
    explanation_letter = models.ForeignKey('compose.Compose', related_name="explanation_letter",
                                           on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10,
                              choices=ATTENDANCE.EXCEPTION_STATUS.CHOICES,
                              default=ATTENDANCE.EXCEPTION_STATUS.DEFAULT)
    manager = models.ForeignKey('user.User', null=True, on_delete=models.SET_NULL, related_name="manager")
    hr_user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, related_name="hr_exceptions")
    worked_time = models.IntegerField(
        null=True, blank=True,
        help_text="Corrected worked time in seconds, set by HR user when handling the exception"
    )

    def __str__(self):
        return f"{self.employee} {self.kind} on {self.attendance} [{self.status}]"


class AttendanceExceptionApproval(models.Model):
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True)
    exception = models.ForeignKey(AttendanceException, on_delete=models.CASCADE, related_name="approvals")
    type = models.CharField(max_length=30, choices=ATTENDANCE.USER_TYPES.CHOICES)
    is_approved = models.BooleanField(null=True)
    decision_note = models.TextField(blank=True, null=True)
    action_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.exception} [{self.type}]"
