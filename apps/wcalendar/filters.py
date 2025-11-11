import django_filters
from django_filters import rest_framework as filters

from apps.wcalendar.models import CalendarModel
from utils.tools import StartDateFilter, EndDateFilter


class CalendarModelFilter(filters.FilterSet):
    created_end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    created_start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    end_date = EndDateFilter(field_name='end_date', lookup_expr='lte')
    start_date = StartDateFilter(field_name='start_date', lookup_expr='gte')
    priority = django_filters.NumberFilter(field_name='priority_id', lookup_expr='exact')
    type = django_filters.CharFilter(field_name='type')

    class Meta:
        model = CalendarModel
        fields = [
            'created_end_date',
            'created_start_date',
            'end_date',
            'priority',
            'start_date',
            'type',
        ]
