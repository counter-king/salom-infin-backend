import django_filters
from django_filters import rest_framework as filters

from apps.company.models import Company, Position, Department
from utils.tools import IntegerListFilter, StringListFilter


class CompanyFilters(filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')
    code = django_filters.CharFilter(field_name='code', lookup_expr='icontains')
    condition = django_filters.CharFilter(field_name='condition')

    class Meta:
        model = Company
        fields = [
            'ids',
            'code',
            'condition',
        ]


class DepartmentFilters(filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')
    code = django_filters.CharFilter(field_name='code', lookup_expr='in')
    condition = StringListFilter(field_name='condition')
    company = django_filters.NumberFilter(field_name='company_id')
    parent = django_filters.NumberFilter(field_name='parent_id')
    parent_code = django_filters.CharFilter(field_name='parent_code', lookup_expr='icontains')

    class Meta:
        model = Department
        fields = [
            'ids',
            'code',
            'condition',
            'company',
            'parent',
            'parent_code',
        ]
