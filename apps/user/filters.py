import django_filters
from django.db import models
from django.db.models import Case, When
from django_filters import rest_framework as filters

from apps.user.models import User, TopSigner
from utils.constants import CONSTANTS
from utils.tools import IntegerListFilter, StringListFilter


class UserFilters(filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')
    status_codes = StringListFilter(field_name='status__code', lookup_expr='in')
    company = django_filters.NumberFilter(field_name='company_id')
    department = django_filters.NumberFilter(field_name='department_id')
    father_name = django_filters.CharFilter(field_name='father_name', lookup_expr='icontains')
    first_name = django_filters.CharFilter(field_name='first_name', lookup_expr='icontains')
    is_registered = django_filters.BooleanFilter(field_name='is_registered')
    is_user_active = django_filters.BooleanFilter(field_name='is_user_active')
    last_name = django_filters.CharFilter(field_name='last_name', lookup_expr='icontains')
    phone = django_filters.CharFilter(field_name='phone', lookup_expr='icontains')
    pinfl = django_filters.CharFilter(field_name='pinfl', lookup_expr='icontains')
    position = django_filters.NumberFilter(field_name='position_id')
    table_number = django_filters.CharFilter(field_name='table_number', lookup_expr='icontains')
    tin = django_filters.CharFilter(field_name='tin', lookup_expr='icontains')
    username = django_filters.CharFilter(field_name='username', lookup_expr='icontains')
    roles = django_filters.NumberFilter(field_name='roles', lookup_expr='in')

    class Meta:
        model = User
        fields = [
            'company',
            'department',
            'father_name',
            'first_name',
            'is_registered',
            'is_user_active',
            'last_name',
            'phone',
            'pinfl',
            'position',
            'table_number',
            'tin',
            'status_codes',
            'username',
            'roles',
        ]

    # def ids_method(self, queryset, name, value):
    #     ids = value.split(',')
    #     user_ids = [int(id) for id in ids]
    #
    #     return queryset.filter(status__code__in=CONSTANTS.USER_STATUSES.CONDITIONS).annotate(
    #         priority=Case(
    #             *[When(id=id, then=pos) for pos, id in enumerate(user_ids)],
    #             default=len(ids),
    #             output_field=models.IntegerField()
    #         )
    #     ).order_by('priority')


class TopSignerFilters(filters.FilterSet):
    ids = IntegerListFilter(field_name='user_id', lookup_expr='in')
    first_name = django_filters.CharFilter(field_name='user__first_name', lookup_expr='icontains')
    last_name = django_filters.CharFilter(field_name='user__last_name', lookup_expr='icontains')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    table_number = django_filters.CharFilter(field_name='user__table_number', lookup_expr='icontains')
    doc_types = django_filters.NumberFilter(field_name='doc_types')

    class Meta:
        model = TopSigner
        fields = [
            'doc_types',
            'first_name',
            'ids',
            'is_active',
            'last_name',
            'table_number',
        ]
