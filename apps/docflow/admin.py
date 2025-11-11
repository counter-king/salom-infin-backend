from django.contrib import admin

from apps.docflow.models import BaseDocument, DocumentFile, Reviewer, Assignment, Assignee


# Register your models here.

@admin.register(BaseDocument)
class BaseDocumentAdmin(admin.ModelAdmin):
    fields = ['title', 'description', 'status', 'delivery_type', 'priority', 'document_type', 'correspondent',
              'journal', 'language', 'code', 'grif', 'register_date', 'register_number', 'outgoing_number',
              'outgoing_date', 'number_of_papers', 'is_deleted']
    list_display = ['register_number', 'register_date', 'status', 'correspondent',
                    'created_date', 'created_by', 'is_deleted']
    search_fields = ['register_number', 'description', 'code', 'outgoing_number', 'id']
    date_hierarchy = 'created_date'
    list_filter = ['status', 'priority', 'is_deleted', 'journal', 'register_date']
    readonly_fields = ['description', 'status', 'delivery_type', 'priority', 'document_type', 'correspondent',
                       'journal', 'language',
                       'code', 'grif', 'register_date', 'register_number', 'outgoing_number', 'outgoing_date',
                       'created_date', 'created_by', 'modified_date', 'modified_by']


@admin.register(DocumentFile)
class DocumentFileAdmin(admin.ModelAdmin):
    list_display = ['document', 'file', 'created_date', 'created_by']
    search_fields = ['document__register_number', 'document__description', 'file__name']


@admin.register(Reviewer)
class ReviewerAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'user', 'status', 'created_date', 'created_by']
    search_fields = ['document__register_number', 'document__description', 'user__username', 'user__first_name',
                     'user__last_name', 'user__phone']
    date_hierarchy = 'created_date'
    list_filter = ['status', 'has_resolution', 'is_read']
    autocomplete_fields = ['user']
    readonly_fields = ['document', 'files', 'comment', 'created_date', 'created_by', 'modified_date', 'modified_by']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'reviewer', 'type', 'is_verified', 'is_project_resolution', 'has_child_resolution']
    search_fields = ['reviewer__document__register_number', 'reviewer__document__description', 'id',
                     'reviewer__user__username', 'reviewer__user__first_name', 'reviewer__user__last_name']
    list_filter = ['type', 'is_project_resolution', 'has_child_resolution']
    date_hierarchy = 'created_date'
    readonly_fields = ['type', 'reviewer', 'parent', 'created_date', 'created_by',
                       'modified_date', 'modified_by']


@admin.register(Assignee)
class AssigneeAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'is_performed', 'is_responsible', 'is_controller', 'is_read']
    search_fields = ['assignment__reviewer__user__username', 'assignment__reviewer__user__first_name',
                     'assignment__reviewer__user__last_name', 'user__username', 'user__first_name', 'user__last_name',
                     'assignment_id']
    list_filter = ['is_performed', 'is_responsible', 'is_controller', 'is_read']
    date_hierarchy = 'created_date'
    readonly_fields = ['assignment', 'user', 'performed_date', 'created_date', 'created_by', 'modified_date',
                       'modified_by']
