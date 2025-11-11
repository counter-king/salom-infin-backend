import django_filters
from django_filters import rest_framework as filters

from apps.docflow.models import BaseDocument, Reviewer, Assignment, Assignee
from utils.constant_ids import get_completed_base_doc_status_id
from utils.tools import StartDateFilter, EndDateFilter, IntegerListFilter, VerifiedFilter


class DocFlowFilters(filters.FilterSet):
    code = django_filters.CharFilter(field_name='code')
    correspondent_id = django_filters.NumberFilter(field_name='correspondent')
    created_end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    created_start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    doc_type_id = django_filters.NumberFilter(field_name='document_type')
    grif = django_filters.CharFilter(field_name='grif')
    journal_id = django_filters.NumberFilter(field_name='journal')
    language_id = django_filters.NumberFilter(field_name='language')
    outgoing_end_date = EndDateFilter(field_name='outgoing_date', lookup_expr='lte')
    outgoing_number = django_filters.CharFilter(field_name='outgoing_number', lookup_expr='icontains')
    outgoing_start_date = StartDateFilter(field_name='outgoing_date', lookup_expr='gte')
    register_end_date = EndDateFilter(field_name='register_date', lookup_expr='lte')
    register_number = django_filters.CharFilter(field_name='register_number', lookup_expr='icontains')
    register_start_date = StartDateFilter(field_name='register_date', lookup_expr='gte')
    reviewer_has_resolution = django_filters.BooleanFilter(field_name='reviewers__has_resolution')
    reviewer_id = django_filters.NumberFilter(field_name='reviewers__user_id')
    reviewer_set = django_filters.BooleanFilter(method='filter_reviewer_set')
    status_id = IntegerListFilter(field_name='status')

    class Meta:
        model = BaseDocument
        fields = [
            'code',
            'correspondent_id',
            'created_end_date',
            'created_start_date',
            'doc_type_id',
            'grif',
            'journal_id',
            'language_id',
            'outgoing_end_date',
            'outgoing_number',
            'outgoing_start_date',
            'register_end_date',
            'register_number',
            'register_start_date',
            'reviewer_has_resolution',
            'reviewer_id',
            'reviewer_set',
            'status_id',
        ]

    def filter_reviewer_set(self, queryset, name, value):
        return queryset.filter(reviewers__isnull=value).distinct()


class ReviewerFilters(filters.FilterSet):
    assignment_is_verified = django_filters.BooleanFilter(field_name='assignments__is_verified')
    assignment_type = django_filters.NumberFilter(field_name='assignments__type')
    code = django_filters.CharFilter(field_name='document__code')
    correspondent_id = django_filters.NumberFilter(field_name='document__correspondent')
    deadline_end_date = EndDateFilter(field_name='assignments__deadline', lookup_expr='lte')
    deadline_start_date = StartDateFilter(field_name='assignments__deadline', lookup_expr='gte')
    doc_type_id = django_filters.NumberFilter(field_name='document__doc_type')
    document_id = django_filters.NumberFilter(field_name='document')
    has_resolution = VerifiedFilter(field_name='has_resolution')
    grif = django_filters.CharFilter(field_name='document__grif')
    is_read = django_filters.BooleanFilter(field_name='is_read')
    journal_id = django_filters.NumberFilter(field_name='document__journal')
    outgoing_end_date = EndDateFilter(field_name='document__outgoing_date', lookup_expr='lte')
    outgoing_number = django_filters.CharFilter(field_name='document__outgoing_number', lookup_expr='icontains')
    outgoing_start_date = StartDateFilter(field_name='document__outgoing_date', lookup_expr='gte')
    read_end_date = EndDateFilter(field_name='read_time', lookup_expr='lte')
    read_start_date = StartDateFilter(field_name='read_time', lookup_expr='gte')
    register_end_date = EndDateFilter(field_name='document__register_date', lookup_expr='lte')
    register_number = django_filters.CharFilter(field_name='document__register_number', lookup_expr='icontains')
    register_start_date = StartDateFilter(field_name='document__register_date', lookup_expr='gte')
    status_id = IntegerListFilter(field_name='status')
    user_id = django_filters.NumberFilter(field_name='user')
    status_type = django_filters.CharFilter(method='filter_status_type')

    class Meta:
        model = Reviewer
        fields = [
            'assignment_is_verified',
            'assignment_type',
            'code',
            'correspondent_id',
            'deadline_end_date',
            'deadline_start_date',
            'doc_type_id',
            'document_id',
            'has_resolution',
            'grif',
            'is_read',
            'journal_id',
            'outgoing_end_date',
            'outgoing_number',
            'outgoing_start_date',
            'read_end_date',
            'read_start_date',
            'register_end_date',
            'register_number',
            'register_start_date',
            'status_id',
            'status_type',
            'user_id',
        ]

    def filter_status_type(self, queryset, name, value):
        done_status_id = get_completed_base_doc_status_id()
        if value == 'in_progress':
            return queryset.filter(has_resolution=False, is_read=True).exclude(status_id=done_status_id)
        else:
            return queryset


class AssignmentFilters(filters.FilterSet):
    code = django_filters.CharFilter(field_name='reviewer__document__code')
    correspondent_id = django_filters.NumberFilter(field_name='reviewer__document__correspondent')
    document_id = django_filters.NumberFilter(field_name='reviewer__document_id')
    doc_type_id = django_filters.NumberFilter(field_name='reviewer__document__doc_type')
    grif = django_filters.CharFilter(field_name='reviewer__document__grif')
    has_child_resolution = django_filters.BooleanFilter(field_name='has_child_resolution')
    is_project_resolution = django_filters.BooleanFilter(field_name='is_project_resolution')
    is_verified = django_filters.BooleanFilter(field_name='is_verified')
    journal_id = django_filters.NumberFilter(field_name='reviewer__document__journal')
    outgoing_end_date = EndDateFilter(field_name='reviewer__document__outgoing_date', lookup_expr='lte')
    outgoing_number = django_filters.CharFilter(field_name='reviewer__document__outgoing_number',
                                                lookup_expr='icontains')
    outgoing_start_date = StartDateFilter(field_name='reviewer__document__outgoing_date', lookup_expr='gte')
    parent_id = django_filters.NumberFilter(field_name='parent_id')
    receipt_end_date = EndDateFilter(field_name='receipt_date', lookup_expr='lte')
    receipt_start_date = StartDateFilter(field_name='receipt_date', lookup_expr='gte')
    register_end_date = EndDateFilter(field_name='reviewer__document__register_date', lookup_expr='lte')
    register_number = django_filters.CharFilter(field_name='reviewer__document__register_number',
                                                lookup_expr='icontains')
    register_start_date = StartDateFilter(field_name='reviewer__document__register_date', lookup_expr='gte')
    reviewer_id = django_filters.NumberFilter(field_name='reviewer_id')
    reviewer_user_id = django_filters.NumberFilter(field_name='reviewer__user_id')
    type = django_filters.NumberFilter(field_name='type')
    status_type = django_filters.CharFilter(method='filter_status_type')

    class Meta:
        model = Assignment
        fields = [
            'code',
            'correspondent_id',
            'doc_type_id',
            'document_id',
            'grif',
            'has_child_resolution',
            'is_project_resolution',
            'is_verified',
            'journal_id',
            'outgoing_end_date',
            'outgoing_number',
            'outgoing_start_date',
            'parent_id',
            'receipt_end_date',
            'receipt_start_date',
            'register_end_date',
            'register_number',
            'register_start_date',
            'reviewer_id',
            'reviewer_user_id',
            'type',
            'status_type',
        ]

    def filter_status_type(self, queryset, name, value):
        done_status_id = get_completed_base_doc_status_id()
        if value == 'in_progress':
            return queryset.filter(is_read=True).exclude(status_id=done_status_id)
        else:
            return queryset


class AssigneeFilters(filters.FilterSet):
    assignment_type = django_filters.NumberFilter(field_name='assignment__type')
    code = django_filters.CharFilter(field_name='assignment__reviewer__document__code')
    correspondent_id = django_filters.NumberFilter(field_name='assignment__reviewer__document__correspondent')
    deadline_end_date = EndDateFilter(field_name='assignment__deadline', lookup_expr='lte')
    deadline_start_date = StartDateFilter(field_name='assignment__deadline', lookup_expr='gte')
    doc_type_id = django_filters.NumberFilter(field_name='assignment__reviewer__document__doc_type')
    document_id = django_filters.NumberFilter(field_name='assignment__reviewer__document')
    grif = django_filters.CharFilter(field_name='assignment__reviewer__document__grif')
    is_read = django_filters.BooleanFilter(field_name='is_read')
    is_verified = django_filters.BooleanFilter(field_name='assignment__is_verified')
    journal_id = django_filters.NumberFilter(field_name='assignment__reviewer__document__journal')
    outgoing_end_date = EndDateFilter(field_name='assignment__reviewer__document__outgoing_date', lookup_expr='lte')
    outgoing_number = django_filters.CharFilter(field_name='assignment__reviewer__document__outgoing_number',
                                                lookup_expr='icontains')
    outgoing_start_date = StartDateFilter(field_name='assignment__reviewer__document__outgoing_date', lookup_expr='gte')
    register_end_date = EndDateFilter(field_name='assignment__reviewer__document__register_date', lookup_expr='lte')
    register_number = django_filters.CharFilter(field_name='assignment__reviewer__document__register_number',
                                                lookup_expr='icontains')
    register_start_date = StartDateFilter(field_name='assignment__reviewer__document__register_date', lookup_expr='gte')
    reviewer_id = django_filters.NumberFilter(field_name='assignment__reviewer__user_id')
    status_id = IntegerListFilter(field_name='status')

    class Meta:
        model = Assignee
        fields = [
            'assignment_type',
            'code',
            'correspondent_id',
            'deadline_end_date',
            'deadline_start_date',
            'doc_type_id',
            'document_id',
            'grif',
            'is_read',
            'is_verified',
            'journal_id',
            'outgoing_end_date',
            'outgoing_number',
            'outgoing_start_date',
            'register_end_date',
            'register_number',
            'register_start_date',
            'reviewer_id',
            'status_id',
        ]
