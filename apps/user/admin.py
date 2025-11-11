from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.contenttypes.models import ContentType
from modeltranslation.admin import TranslationAdmin

from apps.user.models import (
    NotificationModel,
    NotificationType,
    ProjectPermission,
    RoleModel,
    TopSigner,
    User,
    UserDevice,
    UserAssistant,
    UserStatus,
    MySalary,
    AnnualSalary,
    UserEquipment,
    BirthdayReaction,
    BirthdayComment,
    MoodReaction,
    CustomAvatar,
    MySelectedContact,
)


class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation',
                                widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('username',)

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = (
            'username', 'password',
            'first_name', 'last_name',
            'is_superuser', 'groups'
        )

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial["password"]


class UserAdmin(DjangoUserAdmin):
    # The forms to add and change user instances
    form = UserChangeForm
    add_form = UserCreationForm

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User. 'company', 'department', 'position'
    list_display = ('first_name', 'last_name', 'status', 'phone', 'company', 'position', 'is_user_active',)

    list_filter = ('is_user_active', 'is_superuser', 'is_staff', 'is_registered', 'last_login')
    # filter_horizontal = ('groups', 'user_permissions',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (
            'Personal info',
            {'fields': (
                'first_name',
                'last_name',
                'father_name',
                'phone',
                'birth_date',
                'pinfl',
                'tin',
                'gender',
                'avatar',
                'passport_seria',
                'passport_number',
                'passport_issue_date',
                'passport_expiry_date',
                'passport_issued_by',
            )}),
        ('Company info', {'fields': (
            'company',
            'top_level_department',
            'department',
            'department_ids',
            'position',
            'status',
            'begin_work_date',
            'rank',
            'iabs_emp_id',
            'iabs_staffing_id',
            'table_number',
            'ldap_login',
            'cisco',
            'email',
            'work_address',
            'floor',
            'room_number',
            'end_date',
            'leave_end_date',
            'hik_person_code',
        )}),
        ('Permissions', {'fields': (
            'is_superuser',
            'is_staff',
            'is_user_active',
            'is_registered',
            'show_birth_date',
            'show_mobile_number',
            'otp',
            'otp_sent_time',
            'otp_received_time',
            'otp_count',
            'color',
            'date_joined',
            'last_login',
            'last_seen',
            'roles',
            'permissions',
        )}),
    )
    filter_horizontal = ('roles', 'permissions',)
    readonly_fields = (
        'avatar',
        'otp',
        'otp_sent_time',
        'otp_received_time',
        'otp_count',
        'date_joined',
        'end_date',
        'iabs_staffing_id',
        'last_login',
        'last_seen',
        'tin',
        'passport_seria',
        'passport_number',
        'passport_issue_date',
        'passport_expiry_date',
        'passport_issued_by',
    )
    autocomplete_fields = ('company', 'top_level_department', 'department', 'position', 'status')

    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2')
        }),
    )
    search_fields = ('username', 'first_name', 'last_name', 'father_name', 'ldap_login', 'pinfl')
    ordering = ('username',)
    actions = ['delete_selected']


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_version', 'device_type', 'sim_id', 'device_name', 'product_name', 'created_date')
    search_fields = ('user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    date_hierarchy = 'created_date'
    list_filter = ('created_date',)
    readonly_fields = (
        'user',
        'app_version',
        'device_type',
        'sim_id',
        'device_name',
        'product_name',
        'wifi_ip',
        'trip_verification',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    )


@admin.register(UserStatus)
class UserStatusAdmin(TranslationAdmin):
    list_display = ('name', 'code', 'included_in_search', 'strict_condition', 'is_reasonable')
    search_fields = ('name', 'code')
    list_filter = ('included_in_search', 'strict_condition')
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')

    def add_statuses_to_user_search(self, request, queryset):
        queryset.update(included_in_search=True)
        self.message_user(request, 'Status added to user search')

    def remove_statuses_from_user_search(self, request, queryset):
        queryset.update(included_in_search=False)
        self.message_user(request, 'Status removed from user search')

    def make_status_strict_user_search(self, request, queryset):
        queryset.update(strict_condition=True)
        self.message_user(request, 'Status added to strict condition')

    def make_status_non_strict_user_search(self, request, queryset):
        queryset.update(strict_condition=False)
        self.message_user(request, 'Status removed from strict condition')

    def make_status_reasonable(self, request, queryset):
        queryset.update(is_reasonable=True)
        self.message_user(request, 'Status marked as reasonable')

    def make_status_unreasonable(self, request, queryset):
        queryset.update(is_reasonable=False)
        self.message_user(request, 'Status marked as unreasonable')

    actions = [
        'add_statuses_to_user_search',
        'remove_statuses_from_user_search',
        'make_status_strict_user_search',
        'make_status_non_strict_user_search',
        'make_status_reasonable',
        'make_status_unreasonable',
    ]


@admin.register(UserAssistant)
class UserAssistantAdmin(admin.ModelAdmin):
    list_display = ('user', 'assistant', 'is_active', 'created_by', 'created_date')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name', 'assistant__username', 'assistant__first_name',
        'assistant__last_name')
    autocomplete_fields = ('user', 'assistant')
    list_filter = ('is_active',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(TopSigner)
class TopSignerAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_doc_types', 'created_by', 'created_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    filter_horizontal = ('doc_types',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')

    def get_doc_types(self, obj):
        return [doc_type.name for doc_type in obj.doc_types.all()]

    get_doc_types.short_description = 'Document Types'


@admin.register(ProjectPermission)
class ProjectPermissionAdmin(TranslationAdmin):
    list_display = ('name', 'parent', 'content_type', 'value', 'method')
    search_fields = ('name', 'url_path')
    autocomplete_fields = ('parent', 'content_type', 'journal', 'document_type', 'document_sub_type')
    list_filter = ('method',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(RoleModel)
class RoleModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_by', 'created_date')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'app_label', 'model')
    search_fields = ('app_label', 'model')


@admin.register(NotificationModel)
class NotificationModelAdmin(TranslationAdmin):
    list_display = ('name', 'type', 'created_by', 'created_date')
    search_fields = ('name', 'description')
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification', 'is_mute')
    autocomplete_fields = ('user', 'notification')
    list_filter = ('is_mute',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(MySalary)
class MySalaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'pay_name', 'summ')
    autocomplete_fields = ('user',)
    search_fields = ('user__first_name', 'user__last_name')
    readonly_fields = (
        'created_by', 'created_date', 'modified_by', 'modified_date',
        'summ', 'pay_name', 'user', 'period', 'paid')


@admin.register(AnnualSalary)
class AnnualSalaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'month_value', 'monthly_salary')
    autocomplete_fields = ('user',)
    search_fields = ('user__first_name', 'user__last_name')
    readonly_fields = (
        'created_by', 'created_date', 'modified_by',
        'modified_date')


@admin.register(UserEquipment)
class UserEquipmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'card_id', 'inv_num', 'date_oper')
    search_fields = ('user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('user', 'card_id', 'name', 'inv_num', 'date_oper', 'qr_text', 'responsible')


@admin.register(BirthdayReaction)
class BirthdayReactionAdmin(admin.ModelAdmin):
    list_display = ('birthday_user', 'reacted_by', 'reaction', 'created_date')
    search_fields = ('birthday_user__first_name',
                     'birthday_user__last_name',
                     'reacted_by__first_name',
                     'reacted_by__last_name')
    readonly_fields = (
        'birthday_user',
        'reacted_by',
        'reaction',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
        'is_active')


@admin.register(BirthdayComment)
class BirthdayCommentAdmin(admin.ModelAdmin):
    list_display = ('birthday_user', 'commented_by', 'created_date')
    search_fields = ('birthday_user__first_name',
                     'birthday_user__last_name',
                     'commented_by__first_name',
                     'commented_by__last_name')
    readonly_fields = (
        'birthday_user',
        'commented_by',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
        'is_active')


@admin.register(MoodReaction)
class MoodReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'reaction', 'created_date')
    search_fields = ('user__first_name', 'user__last_name',)
    list_filter = ('reaction', 'created_date')
    date_hierarchy = 'created_date'
    readonly_fields = (
        'user',
        'reaction',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
        'is_active')


@admin.register(CustomAvatar)
class CustomAvatarAdmin(admin.ModelAdmin):
    list_display = ('file', 'user', 'created_date')
    autocomplete_fields = ('file', 'user')
    search_fields = ('user__first_name', 'user__last_name', 'file__name')
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


@admin.register(MySelectedContact)
class MySelectedContactAdmin(admin.ModelAdmin):
    list_display = ('user', 'contact', 'created_date')
    autocomplete_fields = ('user', 'contact')
    search_fields = ('user__first_name', 'user__last_name', 'contact__first_name', 'contact__last_name')
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')


admin.site.register(User, UserAdmin)
