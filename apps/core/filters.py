import django_filters
from django_filters import rest_framework as filters

from apps.core.models import BranchManager, DepartmentManager
from utils.tools import VerifiedFilter


class DepartmentManagerFilter(filters.FilterSet):
    department = django_filters.NumberFilter(field_name='department_id')
    user = django_filters.NumberFilter(field_name='user_id')
    is_active = VerifiedFilter(field_name='is_active')
    company = django_filters.NumberFilter(field_name='department__company_id')

    class Meta:
        model = DepartmentManager
        fields = ['department', 'user', 'is_active', 'company']
