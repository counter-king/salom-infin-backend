import django_filters
from django_filters import rest_framework as filters

from apps.hr.models import (
    DailySummary,
    EmployeeSchedule,
    AttendanceException,
    PayrollPeriod,
)
from utils.tools import VerifiedFilter, StartDateFilter, EndDateFilter, StringListFilter

STATUS = ["lateness", "early_leaves", "absent", "on_time"]


class DailySummaryFilter(filters.FilterSet):
    user = django_filters.NumberFilter(field_name='user', lookup_expr='exact')
    department = django_filters.NumberFilter(field_name='user__top_level_department', lookup_expr='exact')
    company = django_filters.NumberFilter(field_name='user__company', lookup_expr='exact')
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    late_minutes = django_filters.NumberFilter(field_name='late_minutes', lookup_expr='gte')
    early_leave_minutes = django_filters.NumberFilter(field_name='early_leave_minutes', lookup_expr='gte')
    absent = VerifiedFilter(field_name='absent', lookup_expr='exact')
    status = django_filters.CharFilter(method='filter_status', lookup_expr='exact')
    has_reason = django_filters.BooleanFilter(field_name='has_reason', lookup_expr='exact')

    class Meta:
        model = DailySummary
        fields = [
            'user',
            'department',
            'start_date',
            'end_date',
            'late_minutes',
            'early_leave_minutes',
            'absent',
            'has_reason',
        ]

    def filter_status(self, queryset, name, value):
        if value not in STATUS:
            return queryset
        if value == "lateness":
            return queryset.filter(late_minutes__gt=0)
        if value == "early_leaves":
            return queryset.filter(early_leave_minutes__gt=0)
        if value == "absent":
            return queryset.filter(absent=True)
        if value == "on_time":
            return queryset.filter(present=True, late_minutes=0)
        return queryset


class EmployeeScheduleFilter(filters.FilterSet):
    employee = django_filters.NumberFilter(field_name='employee')
    top_department = django_filters.NumberFilter(field_name='employee__top_level_department')
    department = django_filters.NumberFilter(field_name='employee__department')
    company = django_filters.NumberFilter(field_name='employee__company')
    start_date = StartDateFilter(field_name='date', lookup_expr='gte')
    end_date = EndDateFilter(field_name='date', lookup_expr='lte')
    is_default = VerifiedFilter(field_name='is_default')

    class Meta:
        model = EmployeeSchedule
        fields = [
            'employee',
            'top_department',
            'department',
            'company',
            'start_date',
            'end_date',
            'is_default',
        ]


class AttendanceExceptionFilter(filters.FilterSet):
    start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    attendance = django_filters.NumberFilter(field_name='attendance')
    employee = django_filters.NumberFilter(field_name='employee')
    reason = django_filters.CharFilter(method='reason')
    status = StringListFilter(field_name='status')
    state = django_filters.CharFilter(method='state_filter')

    class Meta:
        model = AttendanceException
        fields = ['attendance', 'employee', 'reason', 'status', 'state', 'start_date', 'end_date']

    def state_filter(self, queryset, name, value):
        if value == 'has_reason':
            return queryset.filter(reason__isnull=False)
        elif value == 'no_reason':
            return queryset.filter(reason__isnull=True)
        elif value == 'has_letter':
            return queryset.filter(explanation_letter__isnull=False)
        elif value == 'rejected':
            return queryset.filter(status='rejected')
        elif value == 'archived':
            return queryset.filter(status='approved')
        return queryset


class PayrollPeriodFilter(filters.FilterSet):
    company = django_filters.NumberFilter(field_name='company')
    department = django_filters.NumberFilter(field_name='department')
    year = django_filters.NumberFilter(field_name='year')
    month = django_filters.NumberFilter(field_name='month')
    status = StringListFilter(field_name='status')
    type = django_filters.CharFilter(field_name='type')
    mid_pay_date = django_filters.DateFilter(field_name='mid_pay_date', lookup_expr='gte')
    final_pay_date = django_filters.DateFilter(field_name='final_pay_date', lookup_expr='lte')

    class Meta:
        model = PayrollPeriod
        fields = ['company', 'department', 'year', 'month', 'type', 'status', 'mid_pay_date', 'final_pay_date']
