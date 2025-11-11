import django_filters
from django.db.models import Q
from django_filters import rest_framework as filters

from apps.compose.models import (
    Approver,
    BusinessTrip,
    Compose,
    Negotiator,
    Signer,
    Tag,
    TripExpense,
    TripVerification,
    IABSActionHistory,
)
from utils.tools import StartDateFilter, EndDateFilter, VerifiedFilter, IntegerListFilter


class ComposeFilter(filters.FilterSet):
    author = IntegerListFilter(field_name='author_id', lookup_expr='in')
    branches = django_filters.NumberFilter(field_name='receiver__companies')
    # company = django_filters.NumberFilter(field_name='company_id')
    created_end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    created_start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    curator = IntegerListFilter(field_name='curator_id', lookup_expr='in')
    departments = IntegerListFilter(field_name='receiver__departments', lookup_expr='in')
    document_type = django_filters.NumberFilter(field_name='document_type_id')
    document_sub_type = django_filters.NumberFilter(field_name='document_sub_type_id')
    journal = django_filters.NumberFilter(field_name='journal_id')
    organizations = django_filters.NumberFilter(field_name='receiver__organizations')
    register_date = django_filters.DateFilter(field_name='register_date')
    register_number = django_filters.CharFilter(field_name='register_number', lookup_expr='icontains')
    registered_document = django_filters.NumberFilter(field_name='registered_document_id')
    registered_number = django_filters.CharFilter(field_name='registered_document__registered_number',
                                                  lookup_expr='icontains')
    replied_document = django_filters.NumberFilter(field_name='replied_document_id')
    sender = django_filters.NumberFilter(field_name='sender_id')
    signers = IntegerListFilter(field_name='signers__user_id', lookup_expr='in')
    approvers = IntegerListFilter(field_name='approvers__user_id', lookup_expr='in')
    status = IntegerListFilter(field_name='status_id', lookup_expr='in')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    user = django_filters.NumberFilter(field_name='user_id')

    class Meta:
        model = Compose
        fields = [
            'approvers',
            'author',
            'branches',
            # 'company',
            'created_end_date',
            'created_start_date',
            'curator',
            'departments',
            'document_type',
            'document_sub_type',
            'journal',
            'organizations',
            'register_date',
            'register_number',
            'registered_document',
            'registered_number',
            'replied_document',
            'sender',
            'signers',
            'status',
            'title',
            'user',
        ]


class ApproverFilter(filters.FilterSet):
    compose = django_filters.NumberFilter(field_name='compose_id')
    created_end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    created_start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    document_types = IntegerListFilter(field_name='compose__document_type_id', lookup_expr='in')
    document_sub_types = IntegerListFilter(field_name='compose__document_sub_type_id', lookup_expr='in')
    approved = VerifiedFilter(field_name='is_approved')
    journals = IntegerListFilter(field_name='compose__journal_id', lookup_expr='in')
    register_date = django_filters.DateFilter(field_name='compose__register_date')
    register_number = django_filters.CharFilter(field_name='compose__register_number', lookup_expr='icontains')
    registered_document = django_filters.NumberFilter(field_name='compose__registered_document_id')
    replied_document = django_filters.NumberFilter(field_name='compose__replied_document_id')
    sender = django_filters.NumberFilter(field_name='compose__sender_id')
    status = django_filters.NumberFilter(field_name='compose__status_id')
    title = django_filters.CharFilter(field_name='compose__title', lookup_expr='icontains')
    users = IntegerListFilter(field_name='user_id', lookup_expr='in')
    department_recipients = IntegerListFilter(field_name='compose__receiver__departments', lookup_expr='in')
    branch_recipients = IntegerListFilter(field_name='compose__receiver__companies', lookup_expr='in')

    class Meta:
        model = Approver
        fields = [
            'compose',
            'created_end_date',
            'created_start_date',
            'document_types',
            'document_sub_types',
            'approved',
            'journals',
            'register_date',
            'register_number',
            'registered_document',
            'replied_document',
            'sender',
            'status',
            'title',
            'users',
            'department_recipients',
            'branch_recipients',
        ]


class SignerFilter(filters.FilterSet):
    compose = django_filters.NumberFilter(field_name='compose_id')
    created_end_date = EndDateFilter(field_name='created_date', lookup_expr='lte')
    created_start_date = StartDateFilter(field_name='created_date', lookup_expr='gte')
    document_types = IntegerListFilter(field_name='compose__document_type_id', lookup_expr='in')
    document_sub_types = IntegerListFilter(field_name='compose__document_sub_type_id', lookup_expr='in')
    signed = VerifiedFilter(field_name='is_signed')
    journals = IntegerListFilter(field_name='compose__journal_id', lookup_expr='in')
    register_date = django_filters.DateFilter(field_name='compose__register_date')
    register_number = django_filters.CharFilter(field_name='compose__register_number', lookup_expr='icontains')
    registered_document = django_filters.NumberFilter(field_name='compose__registered_document_id')
    replied_document = django_filters.NumberFilter(field_name='compose__replied_document_id')
    sender = django_filters.NumberFilter(field_name='compose__sender_id')
    status = django_filters.NumberFilter(field_name='compose__status_id')
    title = django_filters.CharFilter(field_name='compose__title', lookup_expr='icontains')
    users = IntegerListFilter(field_name='user_id', lookup_expr='in')
    department_recipients = IntegerListFilter(field_name='compose__receiver__departments', lookup_expr='in')
    branch_recipients = IntegerListFilter(field_name='compose__receiver__companies', lookup_expr='in')

    class Meta:
        model = Signer
        fields = [
            'compose',
            'created_end_date',
            'created_start_date',
            'document_types',
            'document_sub_types',
            'signed',
            'journals',
            'register_date',
            'register_number',
            'registered_document',
            'replied_document',
            'sender',
            'status',
            'title',
            'users',
            'department_recipients',
            'branch_recipients',
        ]


class TripVerificationFilter(filters.FilterSet):
    trip = django_filters.NumberFilter(field_name='trip_id')
    company = django_filters.NumberFilter(field_name='company_id')
    trip_user = django_filters.NumberFilter(field_name='trip__user_id')
    verified = VerifiedFilter(field_name='verified')

    class Meta:
        model = TripVerification
        fields = [
            'trip',
            'company',
            'trip_user',
            'verified',
        ]


class BusinessTripFilter(filters.FilterSet):
    destination = django_filters.NumberFilter(method='filter_destination')
    branches = IntegerListFilter(field_name='destinations', lookup_expr='in')
    user = django_filters.NumberFilter(field_name='user_id')
    route = django_filters.CharFilter(field_name='route', lookup_expr='icontains')
    company = django_filters.NumberFilter(field_name='company_id')
    trip_status = django_filters.CharFilter(field_name='trip_status')

    class Meta:
        model = BusinessTrip
        fields = [
            'branches',
            'destination',
            'user',
            'route',
            'company',
            'trip_status',
        ]

    def filter_destination(self, queryset, name, value):
        return queryset.filter(Q(destinations__id=value) | Q(company_id=value)).distinct()


class TripExpenseFilter(filters.FilterSet):
    trip = django_filters.NumberFilter(field_name='trip_id', required=True)
    type = django_filters.NumberFilter(field_name='type_id')
    amount_gte = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_lte = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')

    class Meta:
        model = TripExpense
        fields = [
            'trip',
            'type',
            'amount_gte',
            'amount_lte',
        ]


class NegotiatorFilter(filters.FilterSet):
    user = django_filters.NumberFilter(field_name='user_id')
    negotiation = django_filters.NumberFilter(field_name='negotiation_id')
    doc_type = django_filters.NumberFilter(field_name='negotiation__doc_type_id')
    signed = VerifiedFilter(field_name='is_signed')
    unchecked = VerifiedFilter(field_name='is_signed')

    class Meta:
        model = Negotiator
        fields = [
            'user',
            'negotiation',
            'doc_type',
            'signed',
            'unchecked',
        ]


class TagFilter(filters.FilterSet):
    ids = IntegerListFilter(field_name='id', lookup_expr='in')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    document_sub_type = django_filters.NumberFilter(field_name='document_sub_type_id')

    class Meta:
        model = Tag
        fields = [
            'ids',
            'name',
            'document_sub_type',
        ]


class IABSActionHistoryFilter(filters.FilterSet):
    compose_id = django_filters.NumberFilter(field_name='compose_id')
    action = django_filters.CharFilter(field_name='action')
    status = django_filters.CharFilter(field_name='status')
    request_id = django_filters.CharFilter(field_name='request_id')
    user = django_filters.NumberFilter(field_name='user_id')
    department = django_filters.NumberFilter(field_name='user__top_level_department_id')
    doc_type_id = django_filters.NumberFilter(field_name='compose__document_type_id')
    doc_sub_type_id = django_filters.NumberFilter(field_name='compose__document_sub_type_id')
    start_date = StartDateFilter(field_name='start_date', lookup_expr='gte')
    end_date = EndDateFilter(field_name='end_date', lookup_expr='lte')
    company_id = django_filters.NumberFilter(field_name='compose__company_id')
    type = django_filters.CharFilter(field_name='type')

    class Meta:
        model = IABSActionHistory
        fields = [
            'compose_id',
            'action',
            'status',
            'user',
            'doc_type_id',
            'doc_sub_type_id',
            'start_date',
            'end_date',
            'company_id',
            'request_id',
            'department',
            'type',
        ]
