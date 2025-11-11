from django import forms
from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from apps.reference.models import (
    ActionDescription,
    ActionModel,
    AppVersion,
    CityDistance,
    Correspondent,
    Country,
    DeliveryType,
    DigitalSignInfo,
    District,
    DocumentSubType,
    DocumentTitle,
    DocumentType,
    EditableField,
    EmployeeGroup,
    ErrorMessage,
    ExpenseType,
    FieldActionMapping,
    Journal,
    LanguageModel,
    Priority,
    Region,
    ShortDescription,
    StatusModel,
    AttendanceReason, ExceptionEmployee,
)


@admin.register(ActionDescription)
class ActionDescriptionAdmin(TranslationAdmin):
    list_display = ('description', 'code', 'color', 'icon_name', 'created_by', 'created_date')
    search_fields = ('description', 'code')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(StatusModel)
class StatusModelAdmin(TranslationAdmin):
    list_display = ('name', 'description', 'group', 'is_default', 'is_done', 'is_in_progress')
    list_filter = ('group', 'is_default')
    search_fields = ('name', 'description')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Correspondent)
class CorrespondentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'pinfl', 'tin', 'phone', 'email')
    list_filter = ('type',)
    search_fields = ('name', 'description', 'pinfl', 'tin', 'legal_name', 'first_name', 'last_name', 'father_name')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(EmployeeGroup)
class EmployeeGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(FieldActionMapping)
class FieldActionMappingAdmin(admin.ModelAdmin):
    list_display = ('field_name', 'action_code', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('field_name', 'action_code')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(ShortDescription)
class ShortDescriptionAdmin(TranslationAdmin):
    list_display = ('description', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('description',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(DocumentTitle)
class DocumentTitleAdmin(TranslationAdmin):
    list_display = ('name', 'name_ru', 'is_active', 'created_by', 'created_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(ErrorMessage)
class ErrorMessageAdmin(TranslationAdmin):
    list_display = ('message', 'status', 'status_code', 'code')
    search_fields = ('message', 'code')
    list_filter = ('status', 'status_code')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(ActionModel)
class ActionModelAdmin(admin.ModelAdmin):
    list_display = (
        'action',
        'created_by',
        'created_date',
        'description',
        'new_value',
        'old_value',
        'ip_addr',
        'history_for',
    )
    search_fields = ('new_value', 'old_value', 'description')
    readonly_fields = (
        'created_by', 'modified_by', 'created_date', 'modified_date', 'old_value', 'new_value', 'history_for',
        'ip_addr', 'action', 'description', 'object_id', 'content_type', 'cause_of_deletion')


@admin.register(DocumentType)
class DocumentTypeAdmin(TranslationAdmin):
    list_display = ('id', 'name', 'journal', 'is_for_compose', 'modified_by', 'modified_date')
    search_fields = ('name', 'short_name')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(DocumentSubType)
class DocumentSubTypeAdmin(TranslationAdmin):
    list_display = ('id', 'name', 'document_type', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Journal)
class JournalAdmin(TranslationAdmin):
    list_display = (
        'name',
        'is_auto_numbered',
        'index',
        'is_for_compose',
        'code',
        'sort_order',
        'created_date',
    )
    search_fields = ('name',)
    readonly_fields = ('icon', 'created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'alpha_2', 'alpha_3', 'currency_code', 'status', 'modified_date')
    search_fields = ('name', 'code')
    list_filter = ('status',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Region)
class RegionAdmin(TranslationAdmin):
    list_display = ('name', 'code', 'country', 'modified_by', 'modified_date')
    search_fields = ('name',)
    autocomplete_fields = ('country',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


class CityDistanceForm(forms.ModelForm):
    class Meta:
        model = CityDistance
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        from_city = cleaned_data.get('from_city')
        to_city = cleaned_data.get('to_city')

        if from_city and to_city:
            if from_city == to_city:
                self.add_error('to_city', 'From city and To city cannot be the same.')

            elif CityDistance.objects.filter(
                    from_city=to_city,
                    to_city=from_city
            ).exclude(pk=self.instance.pk).exists():
                self.add_error('to_city',
                               f'A distance from {to_city} to {from_city} already exists. Edit the existing one.')

        return cleaned_data


@admin.register(CityDistance)
class CityDistanceAdmin(admin.ModelAdmin):
    form = CityDistanceForm
    list_display = ('from_city', 'to_city', 'distance', 'created_by', 'created_date')
    search_fields = ('from_city__name', 'to_city__name')
    autocomplete_fields = ('from_city', 'to_city')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(District)
class DistrictAdmin(TranslationAdmin):
    list_display = ('name', 'code', 'region', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(LanguageModel)
class LanguageModelAdmin(TranslationAdmin):
    list_display = ('name', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(DeliveryType)
class DeliveryTypeAdmin(TranslationAdmin):
    list_display = ('name', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Priority)
class PriorityAdmin(TranslationAdmin):
    list_display = ('name', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(DigitalSignInfo)
class DigitalSignInfoAdmin(admin.ModelAdmin):
    fields = (
        'uuid',
        'author',
        'document_id',
        'content',
        'signed',
        'ip_addr',
        'signed_on',
        'type',
        'pkcs7',
        'pkcs7_info',
        'created_date',
        'modified_date',
    )
    list_display = ('uuid', 'author', 'document_id', 'signed', 'ip_addr', 'signed_on', 'type', 'created_date')
    search_fields = ('author__first_name', 'author__last_name', 'author__father_name', 'document_id',)
    date_hierarchy = 'created_date'
    list_filter = ('signed', 'type', 'signed_on')
    readonly_fields = (
        'uuid',
        'document_id',
        'author',
        'content',
        'signed',
        'ip_addr',
        'signed_on',
        'type',
        'pkcs7',
        'pkcs7_info',
        'created_date',
        'modified_date')


@admin.register(ExpenseType)
class ExpenseTypeAdmin(TranslationAdmin):
    list_display = ('name', 'created_by', 'created_date', 'modified_by', 'modified_date')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(EditableField)
class EditableFieldAdmin(admin.ModelAdmin):
    list_display = ('field_name', 'description', 'created_by', 'created_date')
    search_fields = ('field_name', 'description')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ('type', 'version', 'min_version', 'created_by', 'created_date')
    search_fields = ('type',)
    autocomplete_fields = ('file',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(AttendanceReason)
class AttendanceReasonAdmin(TranslationAdmin):
    list_display = ('name', 'description', 'code', 'is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')

@admin.register(ExceptionEmployee)
class ExceptionEmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active',)
    list_filter = ('is_active',)
    ordering = ('-created_date',)
    autocomplete_fields = ('user',)
    search_fields = ('user__first_name', 'user__last_name',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date',)
