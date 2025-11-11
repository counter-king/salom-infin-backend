from django.contrib import admin
from django import forms
from apps.policy.models import Resource, Action, Role, Policy, RoleAssignment
from .logic import compile_condition_json


class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = [
            "role", "resource", "action", "effect",
            "condition_kind",
            "param_departments", "param_owner_field",
            "param_time_start_hhmm", "param_time_end_hhmm",
            "param_journal_ids", "param_doc_type_ids", "param_doc_sub_type_ids",
            "param_advanced_ast", "valid_from", "valid_until",
            "org_key", "priority", "enabled",
        ]
        widgets = {
            "param_departments": forms.Textarea(attrs={"rows": 2, "placeholder": "[42, 77]"}),
            "param_owner_field": forms.TextInput(attrs={"placeholder": "user_id"}),
            "param_time_start_hhmm": forms.TextInput(attrs={"placeholder": "10:00"}),
            "param_time_end_hhmm": forms.TextInput(attrs={"placeholder": "18:00"}),
            "param_journal_ids": forms.Textarea(attrs={"rows": 2, "placeholder": "[1, 3, 7]"}),
            "param_doc_type_ids": forms.Textarea(attrs={"rows": 2, "placeholder": "[10, 11]"}),
            "param_doc_sub_type_ids": forms.Textarea(attrs={"rows": 2, "placeholder": "[1001, 1002]"}),
            "param_advanced_ast": forms.Textarea(attrs={"rows": 6}),
        }

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("condition_kind") or "none"
        if kind == Policy.ConditionKind.SPECIFIC_DEPTS and not cleaned.get("param_departments"):
            self.add_error("param_departments", "Provide at least one department id.")
        if kind == Policy.ConditionKind.TIME_WINDOW:
            if not cleaned.get("param_time_start_hhmm") or not cleaned.get("param_time_end_hhmm"):
                self.add_error("param_time_start_hhmm", "Start/End time required (HH:MM).")
        if kind == Policy.ConditionKind.SPECIFIC_JOURNALS and not cleaned.get("param_journal_ids"):
            self.add_error("param_journal_ids", "Provide journal ids.")
        if kind == Policy.ConditionKind.SPECIFIC_DOC_TYPES and not cleaned.get("param_doc_type_ids"):
            self.add_error("param_doc_type_ids", "Provide document type ids.")
        if kind == Policy.ConditionKind.SPECIFIC_DOC_SUBTYPES and not cleaned.get("param_doc_sub_type_ids"):
            self.add_error("param_doc_sub_type_ids", "Provide document sub type ids.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.condition_json = compile_condition_json(obj)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("key", "display_name", "parent", "description", "created_date")
    search_fields = ("key", "display_name")
    autocomplete_fields = ("parent",)
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("key", "description", "created_date")
    search_fields = ("key",)
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    form = PolicyForm
    list_display = ("role", "resource", "action", "effect", "condition_kind", "priority", "org_key", "enabled")
    list_filter = ("effect", "enabled", "condition_kind")
    search_fields = ("role__name", "resource__key", "action__key", "org_key")
    ordering = ("-priority", "id")
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")
    autocomplete_fields = ("role", "resource", "action")


class InlinePolicy(admin.TabularInline):
    model = Policy
    form = PolicyForm
    extra = 0
    show_change_link = True
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")
    autocomplete_fields = ("resource", "action")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "is_system", "created_date")
    list_filter = ("is_active", "is_system")
    search_fields = ("name",)
    # inlines = [InlinePolicy]
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("role", "user", "group", "org_key", "enabled", "created_date")
    list_filter = ("enabled", "role__name")
    search_fields = ("user__first_name", "user__last_name", "group__name", "role__name", "org_key")
    autocomplete_fields = ("user", "group", "role")
    readonly_fields = ("created_date", "created_by", "modified_date", "modified_by")
