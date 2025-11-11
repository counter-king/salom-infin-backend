from django.contrib import admin
from django.utils.html import format_html

from apps.core.models import (
    BranchManager,
    CacheKey,
    DepartmentManager,
    IngestState,
    PageRanking,
    SQLQuery,
)


@admin.register(CacheKey)
class CacheKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'description', 'expires_in')
    search_fields = ('key', 'description')
    list_filter = ('expires_in',)
    actions = ['clear_cache']
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_date')

    def clear_cache(self, request, queryset):
        for cache_key in queryset:
            cache_key.clear_cache()
        self.message_user(request, 'Cache cleared successfully.')

    clear_cache.short_description = 'Clear Selected Caches'


@admin.register(PageRanking)
class PageRankingAdmin(admin.ModelAdmin):
    list_display = ('page_url', 'rank', 'formatted_comment', 'created_date', 'created_by')
    search_fields = ('page_url', 'comment', 'created_by__first_name', 'created_by__last_name')
    list_filter = ('rank', 'created_date')
    date_hierarchy = 'created_date'
    readonly_fields = (
        'page_url',
        'rank',
        'comment',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    )

    def formatted_comment(self, obj):
        return format_html('<div style="white-space: normal; word-break: break-word; max-width: 300px;">{}</div>',
                           obj.comment)

    formatted_comment.short_description = 'Comment'


@admin.register(SQLQuery)
class SQLQueryAdmin(admin.ModelAdmin):
    list_display = ('query_type', 'created_date', 'created_by')
    search_fields = ('query_type',)
    readonly_fields = (
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    )


@admin.register(DepartmentManager)
class DepartmentManagerAdmin(admin.ModelAdmin):
    list_display = (
        "department",
        "user",
        "is_primary",
        "sort_order",
        "is_active",
        "valid_from",
        "valid_until",
        "modified_date",
    )
    list_filter = ("is_active", "department")
    search_fields = ("department__name", "user__first_name", "user__last_name")
    autocomplete_fields = ("department", "user")
    readonly_fields = ("created_by", "created_date", "modified_by", "modified_date")


@admin.register(BranchManager)
class BranchManagerAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "user",
        "is_primary",
        "sort_order",
        "is_active",
        "valid_from",
        "valid_until",
        "modified_date",
    )
    list_filter = ("is_active", "branch")
    search_fields = ("branch__name", "user__first_name", "user__last_name")
    autocomplete_fields = ("branch", "user")
    readonly_fields = ("created_by", "created_date", "modified_by", "modified_date")


@admin.register(IngestState)
class IngestStateAdmin(admin.ModelAdmin):
    list_display = ("source", "last_success_date", "status", "outage_started_at", "updated_at")
    readonly_fields = ("updated_at",)
    list_filter = ("source", "status", "last_success_date")
    date_hierarchy = "last_success_date"