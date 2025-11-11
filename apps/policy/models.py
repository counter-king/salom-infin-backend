from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.validators import RegexValidator
from django.db import models

from base_model.models import BaseModel

key_validator = RegexValidator(
    regex=r"^[a-z0-9_.:-]+$",
    message="Use lowercase letters, digits, dot/underscore/colon/hyphen."
)


class Resource(BaseModel):
    """
    Business/resource namespace, e.g.:
      'news', 'attendance.daily_summary', 'hr.payroll', 'api.v1.reports'
    """
    key = models.CharField(max_length=128, unique=True, validators=[key_validator])
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey("self", null=True, blank=True,
                               on_delete=models.PROTECT, related_name="children")
    display_name = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class Action(BaseModel):
    """
    Operation on a resource, e.g.:
      'view', 'list', 'create', 'update', 'delete', 'export', 'approve'
    """
    key = models.CharField(max_length=64, unique=True, validators=[key_validator])
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Action"
        verbose_name_plural = "Actions"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class Role(BaseModel):
    """
    Assignable role. Attach policies to roles; assign roles to users and/or groups.
    """
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    is_system = models.BooleanField(
        default=False,
        help_text="Protected role; hide in admin for non-superusers."
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Policy(BaseModel):
    EFFECT_ALLOW = "allow"
    EFFECT_DENY = "deny"
    EFFECT_CHOICES = ((EFFECT_ALLOW, "allow"), (EFFECT_DENY, "deny"))

    class ConditionKind(models.TextChoices):
        NONE = "none", "No condition (full access)"
        OWN_DEPT = "own_dept", "User's department only"
        ASSIGNMENT_SCOPE = "assignment_scope", "Assignment scope (org_key)"
        SPECIFIC_DEPTS = "specific_depts", "Specific departments"
        OWN_OBJECT = "own_object", "Only own objects (by field)"
        OWN_AUTHOR = "own_author", "Only where user is Author"
        OWN_CURATOR = "own_curator", "Only where user is Curator"
        SPECIFIC_JOURNALS = "specific_journals", "Specific journals"
        SPECIFIC_DOC_TYPES = "specific_doc_types", "Specific document types"
        SPECIFIC_DOC_SUBTYPES = "specific_doc_subtypes", "Specific document subtypes"
        TIME_WINDOW = "time_window", "Within business hours"
        ADVANCED = "advanced", "Advanced (builder/JSON)"

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="policies")
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="policies")
    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="policies")

    effect = models.CharField(max_length=8, choices=EFFECT_CHOICES, default=EFFECT_ALLOW)
    condition_kind = models.CharField(max_length=32, choices=ConditionKind.choices, default=ConditionKind.NONE)

    # Parameters for presets (human-friendly)
    param_departments = models.JSONField(default=list, blank=True)  # e.g. [42, 77]
    param_owner_field = models.CharField(max_length=64, blank=True, default="")  # e.g. "user_id"
    param_time_start_hhmm = models.CharField(max_length=5, blank=True, default="")  # "10:00"
    param_time_end_hhmm = models.CharField(max_length=5, blank=True, default="")  # "18:00"
    param_advanced_ast = models.JSONField(default=dict, blank=True)  # optional AST/JSON

    # Compose-specific scoping
    param_journal_ids = models.JSONField(default=list, blank=True)
    param_doc_type_ids = models.JSONField(default=list, blank=True)
    param_doc_sub_type_ids = models.JSONField(default=list, blank=True)

    # Compiled JSONLogic expression (engine uses this)
    condition = models.JSONField(default=dict, blank=True)

    # Optional scope key (e.g., department id)
    org_key = models.CharField(max_length=128, blank=True, default="", validators=[key_validator])

    priority = models.IntegerField(default=0)  # higher evaluated first
    enabled = models.BooleanField(default=True, db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)  # when this policy starts applying
    valid_until = models.DateTimeField(null=True, blank=True)  # when it stops applying

    class Meta:
        verbose_name = "Policy"
        verbose_name_plural = "Policies"
        ordering = ["-priority", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "resource", "action", "org_key", "priority"],
                name="uniq_policy_per_role_res_act_org_priority",
            ),
        ]
        indexes = [
            models.Index(fields=["role", "resource", "action"], name="idx_policy_rra"),
            models.Index(fields=["enabled", "-priority"], name="idx_policy_enabled_prio"),
            models.Index(fields=["org_key"], name="idx_policy_org"),
        ]

    def __str__(self) -> str:
        return f"{self.role}:{self.resource}.{self.action} [{self.effect}] p{self.priority}"


class RoleAssignment(BaseModel):
    """
    Grants a role to a subject (user or group), optionally scoped by org_key.
    If both user and group are set, it applies to both (rare; typically one).
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey('user.User', on_delete=models.CASCADE,
                             null=True, blank=True,
                             related_name="role_assignments")
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              null=True, blank=True,
                              related_name="role_assignments")
    org_key = models.CharField(
        max_length=128, blank=True, default="", validators=[key_validator],
        help_text="Optional scope (e.g., department id). Leave blank for global."
    )
    enabled = models.BooleanField(default=True, db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)  # when this assignment starts
    valid_until = models.DateTimeField(null=True, blank=True)  # when it ends

    class Meta:
        verbose_name = "Role assignment"
        verbose_name_plural = "Role assignments"
        constraints = [
            models.CheckConstraint(
                check=(models.Q(user__isnull=False) | models.Q(group__isnull=False)),
                name="chk_assignment_has_user_or_group",
            ),
            models.UniqueConstraint(
                fields=["role", "user", "org_key"],
                name="uniq_assignment_role_user_org",
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["role", "group", "org_key"],
                name="uniq_assignment_role_group_org",
                condition=models.Q(group__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["role", "user"], name="idx_assign_role_user"),
            models.Index(fields=["role", "group"], name="idx_assign_role_group"),
            models.Index(fields=["org_key"], name="idx_assign_org"),
        ]

    def __str__(self) -> str:
        tgt = self.user or self.group
        scope = self.org_key or "global"
        return f"{self.role} -> {tgt} ({scope})"
