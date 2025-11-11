from django.contrib import admin
from django.db.models import Sum
from modeltranslation.admin import TranslationAdmin

from apps.hr import models


@admin.register(models.PayrollCategory)
class PayrollCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_date')
    search_fields = ('name', 'description')
    list_filter = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date', 'is_active')


@admin.register(models.PayrollSubCategory)
class PayrollSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_date')
    search_fields = ('name', 'description')
    list_filter = ('category',)
    ordering = ('name',)
    autocomplete_fields = ('category',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date', 'is_active')


class BranchTypeFilter(admin.SimpleListFilter):
    title = 'Branch Type'
    parameter_name = 'branch_type'

    def lookups(self, request, model_admin):
        return (
            ('head_office', 'Head Office'),
            ('branch', 'Branch'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'head_office':
            return queryset.filter(company__is_main=True)
        elif self.value() == 'branch':
            return queryset.filter(company__is_main=False)
        return queryset


@admin.register(models.Payroll)
class PayrollAdmin(admin.ModelAdmin):
    fields = ('pay_type', 'company', 'period', 'amount', 'department', 'sub_department', 'division')
    list_display = ('get_category', 'department', 'company', 'period', 'get_amount')
    search_fields = ('pay_type__name', 'department__name', 'company__name')
    list_filter = ('period', 'created_date', BranchTypeFilter, 'pay_type__category')
    date_hierarchy = 'period'
    autocomplete_fields = ('pay_type', 'department', 'company', 'sub_department', 'division')
    readonly_fields = (
        'department',
        'sub_department',
        'division',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date',
    )

    def get_category(self, obj):
        return obj.pay_type.category.name if obj.pay_type else '-'

    def get_amount(self, obj):
        # Format the float with space as thousands separator
        return f"{obj.amount:,.2f}".replace(',', ' ').replace('.', ',')

    get_category.short_description = 'Category'
    get_amount.short_description = 'Amount'

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        category = request.GET.get('pay_type__category__id__exact')
        period_year = request.GET.get('period__year')
        period_month = request.GET.get('period__month')
        branch_type = request.GET.get('branch_type')
        try:
            if category or period_year or period_month or branch_type:
                queryset = response.context_data['cl'].queryset
                total = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
                total_formatted = f"{total:,.2f}".replace(',', ' ').replace('.', ',')

                self.message_user(request, f"Total amount: {total_formatted}", level='info')

        except Exception as e:
            self.message_user(request, f"Error calculating total: {str(e)}", level='error')

        return response


# class CalendarInline(admin.TabularInline):
#     model = models.IABSCalendar
#     extra = 0
#     fields = ('date', 'work_day', 'is_holiday', 'holiday_name')
#     readonly_fields = ('date',)
#     can_delete = False
#     show_change_link = True


@admin.register(models.YearModel)
class YearModelAdmin(admin.ModelAdmin):
    fields = ('year',)
    list_display = ('year',)
    search_fields = ('year',)
    ordering = ('-year',)


@admin.register(models.IABSCalendar)
class IABSCalendarAdmin(admin.ModelAdmin):
    fields = ('year', 'date', 'work_day', 'is_holiday', 'holiday_name', 'holiday_name_ru')
    list_display = ('date', 'year', 'work_day', 'is_holiday', 'holiday_name')
    search_fields = ('year__year', 'holiday_name')
    list_filter = ('is_holiday', 'created_date')
    ordering = ('-date',)
    autocomplete_fields = ('year',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
    date_hierarchy = 'date'


@admin.register(models.AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    fields = ('user', 'event_type', 'event_time', 'source', 'external_id', 'raw_payload')
    list_display = ('user', 'event_type', 'event_time', 'source')
    search_fields = ('user__first_name', 'user__last_name', 'external_id')
    list_filter = ('event_type', 'source', 'created_date')
    ordering = ('-event_time',)
    autocomplete_fields = ('user',)
    readonly_fields = ('created_date', 'modified_date', 'external_id', 'raw_payload')
    date_hierarchy = 'event_time'


@admin.register(models.DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    fields = (
        'user', 'user_status', 'date', 'week_day', 'first_check_in', 'last_check_out', 'worked_seconds',
        'late_minutes', 'early_leave_minutes', 'present', 'absent', 'source_agg',
        'person_id', 'person_code', 'plan_begin_time', 'plan_end_time', 'check_in_status', 'check_out_status'
    )
    list_display = (
        'user', 'date', 'user_status', 'first_check_in', 'last_check_out',
        'worked_seconds', 'late_minutes', 'absent'
    )
    search_fields = ('user__first_name', 'user__last_name')
    list_filter = ('present', 'absent', 'created_date')
    ordering = ('-date',)
    autocomplete_fields = ('user', 'user_status')
    # readonly_fields = (
    #     'first_check_in', 'last_check_out',
    #     'week_day', 'worked_seconds', 'late_minutes',
    #     'early_leave_minutes', 'absent', 'present', 'source_agg',
    #     'person_id', 'person_code', 'plan_begin_time', 'plan_end_time',
    #     'check_in_status', 'check_out_status',
    #     'created_date', 'modified_date')
    date_hierarchy = 'date'


@admin.register(models.WorkSchedule)
class WorkScheduleAdmin(TranslationAdmin):
    fields = (
        'name',
        'start_time',
        'end_time',
        'is_default',
        'created_date',
    )
    list_display = ('name', 'start_time', 'end_time', 'is_default', 'created_date')
    search_fields = ('name',)
    list_filter = ('is_default', 'created_date')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date',)


@admin.register(models.EmployeeSchedule)
class EmployeeScheduleAdmin(admin.ModelAdmin):
    list_display = ("employee", "schedule", "is_default", "modified_by", "modified_date")
    search_fields = ("employee__first_name", "employee__last_name")
    list_filter = ("schedule", "created_date", "is_default")
    autocomplete_fields = ("employee", "schedule")
    readonly_fields = ("created_by", "modified_by", "created_date", "modified_date")


@admin.register(models.HRBranchScope)
class HRBranchScopeAdmin(admin.ModelAdmin):
    list_display = ("id", "hr_user", "branch", "can_approve", "valid_from", "valid_until")
    list_filter = ("can_approve", "created_date")
    search_fields = ("hr_user__first_name", "hr_user__last_name", "branch__name")
    autocomplete_fields = ("hr_user", "branch")
    readonly_fields = ("created_by", "modified_by", "created_date", "modified_date")


@admin.register(models.HRDepartmentScope)
class HRDepartmentScopeAdmin(admin.ModelAdmin):
    list_display = ("id", "hr_user", "department", "can_approve", "valid_from", "valid_until")
    list_filter = ("can_approve", "department")
    search_fields = ("hr_user__first_name", "hr_user__last_name", "department__name")
    autocomplete_fields = ("hr_user", "department")
    readonly_fields = ("created_by", "modified_by", "created_date", "modified_date")


class AttendanceExceptionApprovalInline(admin.TabularInline):
    model = models.AttendanceExceptionApproval
    fields = ('user', 'type', 'is_approved', 'decision_note', 'action_time')
    autocomplete_fields = ('user',)
    readonly_fields = ('decision_note', 'action_time', 'is_approved')
    extra = 0


@admin.register(models.AttendanceException)
class AttendanceExceptionAdmin(admin.ModelAdmin):
    list_display = ("employee", "reason", "kind", "status", "created_date")
    list_filter = ("status", "created_date")
    search_fields = ("employee__first_name", "employee__last_name")
    autocomplete_fields = ("employee", "attendance", "reason")
    readonly_fields = (
        "manager", "hr_user",
        "attendance", "worked_time", "attachments",
        "created_by", "modified_by",
        "created_date", "modified_date"
    )
    inlines = (AttendanceExceptionApprovalInline,)


@admin.register(models.PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('get_name', 'year', 'month', 'status', 'employee_count', 'created_date')
    search_fields = ('company__name', "department__name")
    list_filter = ('status', 'type', 'created_date', 'mid_locked', 'final_locked')
    ordering = ('-year', '-month')
    autocomplete_fields = ('company', "department")
    readonly_fields = (
        'created_by', 'modified_by',
        'created_date', 'modified_date',
    )
    date_hierarchy = 'created_date'

    def get_name(self, obj):
        if obj.type == 'department':
            return obj.department.name if obj.department else 'empty'
        elif obj.type == 'branch':
            return obj.company.name if obj.company else 'empty'
        return 'N/A'

    get_name.short_description = 'Name'


@admin.register(models.PayrollRow)
class PayrollRowAdmin(admin.ModelAdmin):
    list_display = ('employee',
                    'period',
                    'department',
                    'total_hours',
                    'total_vacation',
                    'total_sick',
                    'total_trip',
                    'total_absent')
    search_fields = ('employee__first_name', 'employee__last_name', 'department__name')
    list_filter = ('created_date',)
    autocomplete_fields = ('employee', 'department', 'period')
    readonly_fields = (
        'created_by', 'modified_by',
        'created_date', 'modified_date',
    )
    date_hierarchy = 'created_date'


@admin.register(models.PayrollCell)
class PayrollCellAdmin(admin.ModelAdmin):
    list_display = ('date', 'code', 'kind', 'hours', 'row')
    search_fields = ('row__employee__first_name', 'row__employee__last_name', 'code')
    list_filter = ('kind', 'date', 'created_date')
    autocomplete_fields = ('row',)
    readonly_fields = (
        'created_by', 'modified_by',
        'created_date', 'modified_date',
    )
    date_hierarchy = 'date'


@admin.register(models.PayrollApproval)
class PayrollApprovalAdmin(admin.ModelAdmin):
    list_display = ('period', 'user', 'decided', 'approved', 'decided_at')
    search_fields = ('period__company__name', 'user__first_name', 'user__last_name')
    list_filter = ('approved', 'decided', 'decided_at')
    autocomplete_fields = ('period', 'user')
    readonly_fields = (
        'period', 'user', 'note',
        'decided_at', 'approved', 'decided'
    )
    date_hierarchy = 'decided_at'
