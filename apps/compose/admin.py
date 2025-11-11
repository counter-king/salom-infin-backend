from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from apps.compose.models import (
    Approver,
    BusinessTrip,
    Compose,
    ComposeStatus,
    ComposeLink,
    Signer,
    Tag,
    TripVerification,
    TripExpense,
    Negotiation,
    NegotiationType,
    NegotiationSubType,
    NegotiationInstance,
    Negotiator,
    Booking,
    BookingSegment,
    Passenger,
    TripPlan,
    VisitedPlace,
    TripPlace,
    IABSActionHistory,
    IABSRequestCallHistory,
)


@admin.register(BusinessTrip)
class BusinessTripAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_date', 'start_date', 'end_date', 'company', 'notice', 'order', 'travel_paper')
    readonly_fields = (
        'user',
        'group_id',
        'start_date',
        'end_date',
        'destinations',
        'locations',
        'tags',
        'notice',
        'order',
        'travel_paper',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date',
    )
    autocomplete_fields = ('user', 'notice', 'order', 'travel_paper', 'company')
    search_fields = ('id', 'user__username', 'user__first_name', 'user__last_name')


@admin.register(Tag)
class TagAdmin(TranslationAdmin):
    list_display = ('name', 'document_sub_type')
    search_fields = ('name',)
    autocomplete_fields = ('document_sub_type',)
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(ComposeStatus)
class ComposeStatusAdmin(TranslationAdmin):
    list_display = ('name', 'is_default', 'is_draft', 'is_approve', 'declined_from_approver', 'declined_from_signer')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Compose)
class ComposeAdmin(admin.ModelAdmin):
    fields = (
        'document_type',
        'document_sub_type',
        'title',
        'register_number',
        'register_number_int',
        'register_date',
        'is_signed',
        'status',
        'trip_notice_id',
        'user',
        'check_id',
        'sender',
        'company',
        'journal',
        'receiver',
        'author',
        'curator',
        'created_date',
        'modified_date',
        'created_by',
        'modified_by',
    )
    list_display = (
        'document_type',
        'document_sub_type',
        'register_number',
        'register_date',
        'status',
        'author',
        'created_date')
    list_filter = ('status', 'document_type')
    search_fields = ('title', 'register_number', 'short_description')
    date_hierarchy = 'created_date'
    readonly_fields = (
        'author',
        'author',
        'check_id',
        'user',
        'trip_notice_id',
        'status',
        'company',
        'created_by',
        'created_date',
        'curator',
        'document_sub_type',
        'document_type',
        'journal',
        'modified_by',
        'modified_date',
        'receiver',
        'register_number',
        'register_number_int',
        'registered_document',
        'replied_document',
        'sender',
        'status',
    )


@admin.register(ComposeLink)
class ComposeLinkAdmin(admin.ModelAdmin):
    list_display = ('link_type', 'from_compose', 'to_compose', 'created_date')
    autocomplete_fields = ('from_compose', 'to_compose')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
    search_fields = ('compose__register_number', 'link_type')


@admin.register(Approver)
class ApproverAdmin(admin.ModelAdmin):
    list_display = ('compose', 'user', 'is_approved', 'action_date', 'created_date')
    list_filter = ('is_approved',)
    readonly_fields = (
        'compose',
        'user',
        'comment',
        'action_date',
        'read_time',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date')
    autocomplete_fields = ('compose', 'user')
    search_fields = ('compose__title', 'user__username', 'user__first_name', 'user__last_name')


@admin.register(Signer)
class SignerAdmin(admin.ModelAdmin):
    list_display = ('compose', 'user', 'type', 'is_signed', 'is_all_approved', 'action_date', 'created_date')
    list_filter = ('is_signed', 'is_all_approved', 'type')
    autocomplete_fields = ('compose', 'user')
    readonly_fields = (
        'compose',
        'user',
        'comment',
        'read_time',
        'action_date',
        'certificate_info',
        'pkcs7',
        'comment',
        'type',
        'resolution_text',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date')
    search_fields = ('compose__title', 'user__username', 'user__first_name', 'user__last_name')


@admin.register(TripVerification)
class TripVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'trip',
        'verified',
        'arrived_at',
        'left_at',
        'region',
        'is_sender',
    )
    list_filter = ('verified',)
    autocomplete_fields = ('trip', 'company')
    readonly_fields = (
        'trip',
        'arrived_lat',
        'arrived_lng',
        'arrived_address',
        'left_lat',
        'left_lng',
        'left_address',
        'arrived_verified_by',
        'left_verified_by',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date')
    search_fields = (
        'trip__route',
        'user__username',
        'user__first_name',
        'user__last_name',
    )


@admin.register(TripPlace)
class TripPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'lat', 'lng', 'created_date', 'created_by')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
    search_fields = ('name',)
    date_hierarchy = 'created_date'


@admin.register(VisitedPlace)
class VisitedPlaceAdmin(admin.ModelAdmin):
    list_display = ('place', 'trip_verification', 'created_date', 'created_by')
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')
    search_fields = ('place__name',)
    autocomplete_fields = ('place', 'trip_verification')
    date_hierarchy = 'created_date'


@admin.register(TripExpense)
class TripExpenseAdmin(admin.ModelAdmin):
    list_display = ('type', 'trip', 'amount', 'date', 'created_date', 'created_by')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    readonly_fields = ('file', 'comment', 'created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = ('compose', 'created_date', 'created_by')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    search_fields = ('text', 'compose__register_number')
    readonly_fields = (
        'compose',
        'users',
        'text',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date',
    )


@admin.register(NegotiationType)
class NegotiationTypeAdmin(TranslationAdmin):
    list_display = ('name', 'created_date', 'modified_date', 'created_by', 'modified_by')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(NegotiationSubType)
class NegotiationSubTypeAdmin(TranslationAdmin):
    list_display = ('name', 'doc_type', 'created_date', 'modified_date', 'created_by', 'modified_by')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Negotiation)
class NegotiationAdmin(admin.ModelAdmin):
    list_display = ('id', 'doc_type', 'title', 'modified_date', 'modified_by')
    fields = ('doc_type', 'doc_sub_type', 'users', 'created_by', 'modified_by', 'created_date', 'modified_date')
    filter_horizontal = ('users',)
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    readonly_fields = ('created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(NegotiationInstance)
class NegotiationInstanceAdmin(admin.ModelAdmin):
    list_display = ('negotiation', 'doc_type', 'created_date', 'modified_date', 'created_by', 'modified_by')
    fields = ('negotiation', 'doc_type', 'doc_sub_type', 'created_by', 'modified_by', 'created_date', 'modified_date')
    list_filter = ('created_date',)
    date_hierarchy = 'created_date'
    readonly_fields = ('negotiation', 'doc_type', 'created_by', 'modified_by', 'created_date', 'modified_date')


@admin.register(Negotiator)
class NegotiatorAdmin(admin.ModelAdmin):
    list_display = ('negotiation', 'user', 'is_signed', 'action_date', 'read_time')
    list_filter = ('is_signed', 'action_date')
    date_hierarchy = 'action_date'
    readonly_fields = (
        'negotiation',
        'user',
        'comment',
        'read_time',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date')
    search_fields = ('negotiation__id', 'user__username', 'user__first_name', 'user__last_name')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'type',
        'route',
        'total_price',
        'compose',
        'created_by',
        'created_date'
    ]
    list_filter = ['type', 'created_date', 'route']
    date_hierarchy = 'created_date'
    search_fields = ['compose__id']
    readonly_fields = [
        'type',
        'total_price',
        'compose',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date'
    ]


@admin.register(BookingSegment)
class BookingSegmentAdmin(admin.ModelAdmin):
    list_display = [
        'booking',
        'departure_city',
        'arrival_city',
        'departure_date',
        'arrival_date',
        'price',
        'segment_class'
    ]
    list_filter = ['departure_date', 'arrival_date']
    date_hierarchy = 'created_date'
    search_fields = ['booking__id', 'departure_city__name', 'arrival_city__name']
    readonly_fields = [
        'booking',
        'departure_city',
        'arrival_city',
        'departure_date',
        'departure_end_date',
        'arrival_date',
        'price',
        'flight_number',
        'segment_class',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date'
    ]


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'booking',
        'created_date'
    ]
    list_filter = ['created_date']
    date_hierarchy = 'created_date'
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'user',
        'booking',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date'
    ]


@admin.register(IABSActionHistory)
class IABSActionHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'status',
        'type',
        'action',
        'user',
        'result',
        'iabs_id',
        'created_date'
    ]
    list_filter = ['created_date', 'status', 'action', 'type']
    date_hierarchy = 'created_date'
    search_fields = ['user__first_name', 'user__last_name', 'iabs_id', 'request_id']
    readonly_fields = [
        'action',
        'request_id',
        'compose',
        'content_type',
        'object_id',
        'endpoint',
        'request_body',
        'response_body',
        'result',
        'user',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
        'is_active',
    ]


@admin.register(IABSRequestCallHistory)
class IABSRequestCallHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'action_history',
        'caller',
        'requested_date',
        'status',
        'response_text',
    ]
    list_filter = ['created_date', 'status']
    search_fields = ['request_id', 'response_text']
    date_hierarchy = 'created_date'
    readonly_fields = [
        'action_history',
        'caller',
        'request_id',
        'requested_date',
        'status',
        'request_body',
        'response_body',
        'response_code',
        'response_text',
        'created_by',
        'created_date',
        'modified_by',
        'modified_date',
    ]
