from django.contrib import admin

from apps.notification.models import (
    TelegramProfile,
    TelegramNotificationLog,
    NotificationTemplate,
    TelegramPairRequest,
)


@admin.register(TelegramProfile)
class TelegramProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat_id', 'phone', 'username', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'phone')
    readonly_fields = (
        'user', 'chat_id', 'phone', 'username', 'language',
        'created_date', 'created_by', 'modified_date', 'modified_by'
    )
    autocomplete_fields = ('user',)


@admin.register(TelegramNotificationLog)
class TelegramNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat_id', 'template', 'status', 'attempts', 'sent_at')
    search_fields = ('user__first_name', 'user__last_name')
    readonly_fields = ('created_date', 'created_by', 'modified_date', 'modified_by')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    autocomplete_fields = ('user',)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('key', 'lang', 'content', 'is_active')
    readonly_fields = ('created_date', 'created_by', 'modified_date', 'modified_by')
    list_filter = ('lang', 'key', 'created_date')


@admin.register(TelegramPairRequest)
class TelegramPairRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'telegram_username', 'approved')
    search_fields = ('user__first_name', 'user__last_name', 'telegram_username')
    readonly_fields = (
        'user',
        'created_at',
        'expires_at',
        'telegram_id',
        'telegram_username',
        'telegram_phone',
        'confirmation_code',
        'approved',
        'approved_at',
    )
    list_filter = ('approved', 'created_at', 'approved_at')
    ordering = ('-created_at',)
