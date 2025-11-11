from django.contrib import admin

from apps.wcalendar.models import CalendarModel, CalendarParticipant


@admin.register(CalendarModel)
class CalendarModelAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'start_date', 'end_date', 'priority', 'type', 'organizer', 'created_by', 'created_date')
    list_filter = ('priority', 'type', 'created_date', 'start_date')
    date_hierarchy = 'created_date'
    autocomplete_fields = ('organizer',)
    search_fields = ('title', 'description', 'organizer__first_name', 'organizer__last_name')
    readonly_fields = (
        'start_date', 'end_date', 'attachments', 'description', 'created_by', 'created_date', 'modified_by',
        'modified_date', 'is_active')


@admin.register(CalendarParticipant)
class CalendarParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'calendar', 'is_informed', 'is_accepted', 'created_by', 'created_date')
    list_filter = ('is_informed', 'is_accepted', 'created_date')
    date_hierarchy = 'created_date'
    autocomplete_fields = ('user',)
    search_fields = ('calendar__title', 'user__first_name', 'user__last_name')
    readonly_fields = ('calendar', 'created_by', 'created_date', 'modified_by', 'modified_date', 'is_active')
