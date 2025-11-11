import django_filters
# from django_filters import rest_framework as filters
from apps.reference.models import StatusModel, Correspondent, EmployeeGroup, ShortDescription, Region, Country
from utils.tools import IntegerListFilter


class StatusModelFilter(django_filters.FilterSet):
    group = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = StatusModel
        fields = ['group', 'name', 'description']


class CorrespondentFilter(django_filters.FilterSet):
    phone = django_filters.CharFilter(lookup_expr='icontains')
    tin = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')
    type = django_filters.CharFilter(lookup_expr='icontains')
    email = django_filters.CharFilter(lookup_expr='icontains')
    first_name = django_filters.CharFilter(lookup_expr='icontains')
    last_name = django_filters.CharFilter(lookup_expr='icontains')
    father_name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Correspondent
        fields = ['phone', 'tin', 'name', 'type', 'email', 'first_name', 'last_name', 'father_name']


class EmployeeGroupFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = EmployeeGroup
        fields = ['name']


class RegionFilters(django_filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')
    code = django_filters.CharFilter(field_name='code', lookup_expr='icontains')
    country = django_filters.NumberFilter(field_name='country')

    class Meta:
        model = Region
        fields = [
            'ids',
            'code',
            'country',
        ]

class CountryFilters(django_filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = Country
        fields = [
            'ids',
        ]
