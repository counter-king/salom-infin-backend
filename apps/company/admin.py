from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from apps.company.models import Company, Position, Department, EnvModel
from apps.company.tasks import recalculate_sub_department_count
from utils.tools import get_children


@admin.register(Company)
class CompanyAdmin(TranslationAdmin):
    list_display = ('name', 'code', 'local_code', 'condition', 'env_id', 'region', 'created_date')
    search_fields = ('name', 'code', 'local_code', 'phone')
    list_filter = ('condition', 'env_id', 'is_main')
    autocomplete_fields = ('region',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Position)
class PositionAdmin(TranslationAdmin):
    list_display = ('code', 'name', 'condition', 'created_date', 'modified_date')
    search_fields = ('name', 'code')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
    fields = (
        'name',
        'code',
        'iabs_post_id',
        'iabs_level_code',
        'condition',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    )


@admin.register(Department)
class DepartmentAdmin(TranslationAdmin):
    list_display = ('code', 'parent_code', 'name', 'company', 'condition', 'sub_department_count', 'dep_index',)
    search_fields = ('name', 'code', 'parent_code', 'company__name')
    list_filter = ('condition', 'company__local_code')
    readonly_fields = (
        'sub_department_count',
        'level',
        'iabs_dept_id',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date',
    )
    autocomplete_fields = ('parent', 'company')
    fields = (
        'level',
        'sub_department_count',
        'iabs_dept_id',
        'code',
        'parent_code',
        'name',
        'parent',
        'company',
        'condition',
        'dep_index',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    )
    actions = ['activate_departments', 'deactivate_departments', 'recalculate_sub_department_count']

    @admin.action(description='Activate selected departments')
    def activate_departments(self, request, queryset):
        queryset.update(condition='A')
        self.message_user(request, 'Selected departments have been activated.')

    @admin.action(description='Deactivate selected departments')
    def deactivate_departments(self, request, queryset):
        queryset.update(condition='P')
        self.message_user(request, 'Selected departments have been deactivated.')

    @admin.action(description='Recalculate sub department count')
    def recalculate_sub_department_count(self, request, queryset):
        for department in queryset:
            recalculate_sub_department_count(department.id)
        self.message_user(request, 'Sub department count has been recalculated.')


@admin.register(EnvModel)
class EnvModelAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_uz', 'name_ru', 'created_by', 'created_date')
    search_fields = ('name', 'code')
    list_filter = ('code',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
