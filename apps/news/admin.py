from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from apps.news.models import (
    News,
    NewsCategory,
    NewsTag,
    NewsContent,
    NewsViewer,
    NewsComment,
    NewsLike,
    NewsModerationHistory
)


@admin.register(NewsCategory)
class NewsCategoryAdmin(TranslationAdmin):
    list_display = ['name', 'color', 'created_date', 'created_by']
    list_filter = ['created_date']
    search_fields = ['name']
    readonly_fields = ['created_by', 'created_date', 'modified_by', 'modified_date']


@admin.register(NewsContent)
class NewsContentAdmin(admin.ModelAdmin):
    list_display = ['news', 'type', 'created_date', 'created_by']
    list_filter = ['type', 'created_date']
    search_fields = ['content', 'news__title']


class NewsContentInline(admin.TabularInline):  # Use TabularInline for inlines
    model = NewsContent
    extra = 1  # Number of empty forms to display
    fields = ['news', 'type', 'content', 'file']
    autocomplete_fields = ['file']
    readonly_fields = ['file', 'created_date', 'created_by', 'modified_date', 'modified_by']


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'category',
        'status',
        'view_counts',
        'like_counts',
        'created_date',
        'created_by',
    ]
    list_filter = ['category', 'created_date']
    search_fields = ['title', 'description']
    date_hierarchy = 'created_date'
    filter_horizontal = ['tags']
    inlines = [NewsContentInline]
    readonly_fields = ['image',
                       'galleries',
                       'created_by',
                       'created_date',
                       'modified_by',
                       'modified_date',
                       'view_counts',
                       'like_counts',
                       'status']

    @admin.display(description='Publish selected news')
    def publish_news(self, request, queryset):
        queryset.update(status='published')

    @admin.display(description='Unpublish selected news')
    def unpublish_news(self, request, queryset):
        queryset.update(status='draft')

    @admin.display(description="Send to moderator")
    def send_to_moderator(self, request, queryset):
        queryset.update(status='pending')

    @admin.display(description='Archive selected news')
    def archive_news(self, request, queryset):
        queryset.update(status='archived')

    @admin.action(description='Calculate like counts')
    def calculate_like_counts(self, request, queryset):
        for news in queryset:
            news.like_counts = news.likes.filter(emoji__isnull=False).count()
            news.save()

    actions = ['publish_news', 'send_to_moderator', 'unpublish_news', 'archive_news', 'calculate_like_counts']


@admin.register(NewsTag)
class NewsTagAdmin(TranslationAdmin):
    list_display = ['name', 'created_date', 'created_by']
    list_filter = ['created_date']
    search_fields = ['name']
    filter_horizontal = ['categories']
    readonly_fields = ['created_by', 'created_date', 'modified_by', 'modified_date']


@admin.register(NewsViewer)
class NewsViewerAdmin(admin.ModelAdmin):
    list_display = ['news', 'viewer', 'created_date']
    list_filter = ['created_date']
    date_hierarchy = 'created_date'
    search_fields = ['news__title', 'viewer__username']
    readonly_fields = [
        'news',
        'viewer',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    ]


@admin.register(NewsComment)
class NewsCommentAdmin(admin.ModelAdmin):
    list_display = ['news', 'user', 'top_level_comment_id', 'created_date']
    list_filter = ['created_date']
    search_fields = ['news__title', 'comment', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'comment',
        'user',
        'replied_to',
        'top_level_comment_id',
        'created_date',
        'modified_by',
        'modified_date',
    ]


@admin.register(NewsLike)
class NewsLikeAdmin(admin.ModelAdmin):
    list_display = ['news', 'user', 'emoji', 'created_date', 'modified_date']
    list_filter = ['created_date', 'emoji']
    date_hierarchy = 'created_date'
    search_fields = ['news__title', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'news',
        'emoji',
        'user',
        'created_date',
        'modified_by',
        'modified_date',
    ]


@admin.register(NewsModerationHistory)
class NewsModerationModel(admin.ModelAdmin):
    list_display = ['news', 'status', 'created_by', 'created_date']
    list_filter = ['status', 'created_date']
    date_hierarchy = 'created_date'
    search_fields = ['news__title']
    readonly_fields = [
        'news',
        'description',
        'status',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    ]
