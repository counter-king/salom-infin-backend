import django_filters
from django_filters import rest_framework as filters

from apps.news.models import (
    News,
)
from utils.tools import StartDateFilter, EndDateFilter, IntegerListFilter


class NewsFilter(filters.FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    categories = IntegerListFilter(field_name='category', lookup_expr='in')
    tags = IntegerListFilter(field_name='tags', lookup_expr='in')
    start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    exclude_id = django_filters.NumberFilter(method='exclude_id_filter')
    status = django_filters.BaseInFilter(field_name='status', lookup_expr='in')

    class Meta:
        model = News
        fields = [
            'title',
            'category',
            'tags',
            'start_date',
            'end_date',
            'status',
        ]

    def exclude_id_filter(self, queryset, name, value):
        return queryset.exclude(id=value)
