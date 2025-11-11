from rest_framework import serializers

from apps.company.serializers import (
    MiniCompanySerializer,
)
from apps.compose.models import (
    BusinessTrip,
    TripVerification,
    TripExpense,
    Booking,
    BookingSegment,
    Passenger,
    TripPlan,
    VisitedPlace,
    TripPlace,
    Tag,
)
from apps.reference.serializers import RegionSerializer, CountryCreateSerializer
from apps.user.serializers import UserSerializer
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField


class PassengerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(
        model='user.User',
        extra_field=['full_name', 'first_name', 'last_name',
                     'color', 'id', 'position', 'status', 'cisco', 'avatar',
                     'top_level_department', 'department', 'company', 'email'],
        required=False
    )

    class Meta:
        model = Passenger
        fields = [
            'id',
            'user',
            'booking'
        ]


class BookingSegmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    departure_city = SelectItemField(model='reference.Region', extra_field=['id', 'name'], required=False)
    arrival_city = SelectItemField(model='reference.Region', extra_field=['id', 'name'], required=False)

    class Meta:
        model = BookingSegment
        fields = [
            'id',
            'departure_city',
            'arrival_city',
            'departure_date',
            'departure_end_date',
            'arrival_date',
            'booking',
            'price',
            'segment_class',
        ]


class BookingSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    passengers = PassengerSerializer(required=False, many=True)
    segments = BookingSegmentSerializer(required=False, many=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'type',
            'total_price',
            'compose',
            'route',
            'segments',
            'passengers'
        ]

    # def create(self, validated_data):
    #     passengers = validated_data.pop('passengers', [])
    #     segments = validated_data.pop('segments', [])
    #     booking = Booking.objects.create(**validated_data)
    #     self._create_booking_data(booking, passengers, segments)
    #
    #     return booking
    #
    # def _create_booking_data(self, booking, passengers, segments):
    #     for passenger in passengers:
    #         Passenger.objects.create(booking=booking, **passenger)
    #
    #     for segment in segments:
    #         BookingSegment.objects.create(booking=booking, **segment)
    #
    # def update(self, instance, validated_data):
    #     passengers = validated_data.pop('passengers', [])
    #     segments = validated_data.pop('segments', [])
    #     instance = super(BookingSerializer, self).update(instance, validated_data)
    #     self._update_booking_data(instance, passengers, segments)
    #
    #     return instance
    #
    # def _update_booking_data(self, instance, passengers, segments):
    #     for passenger in passengers:
    #         Passenger.objects.update_or_create(booking=instance, **passenger)
    #
    #     for segment in segments:
    #         BookingSegment.objects.update_or_create(booking=instance, **segment)


class TagCreateForTripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'name_uz', 'name_ru']

    def to_internal_value(self, data):
        return data.get('id')


class BusinessTripBaseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(
        model='user.User',
        extra_field=['full_name', 'first_name', 'last_name',
                     'color', 'id', 'position', 'status', 'cisco', 'avatar',
                     'top_level_department', 'department', 'company', 'email', 'iabs_emp_id'],
        required=False
    )
    destinations = MiniCompanySerializer(many=True, read_only=True)
    locations = RegionSerializer(many=True, read_only=True)
    countries = CountryCreateSerializer(many=True, required=False)
    companies = serializers.ListField(
        required=False, write_only=True, child=serializers.IntegerField()
    )
    regions = serializers.ListField(
        required=False, write_only=True, child=serializers.IntegerField()
    )
    tags = TagCreateForTripSerializer(many=True, required=False)
    trip_status = serializers.CharField(read_only=True)
    sender_company = SelectItemField(model='company.Company', extra_field=['id', 'name', 'code', 'region'],
                                     required=False)

    class Meta:
        model = BusinessTrip
        fields = [
            'id',
            'start_date',
            'end_date',
            'end_date_2',
            'destinations',
            'countries',
            'user',
            'route',
            'created_date',
            'modified_date',
            'companies',
            'company',
            'regions',
            'locations',
            'tags',
            'group_id',
            'sender_company',
            'trip_status',
            'trip_type',
            'is_active',
            'parent'
        ]


class BusinessTripSerializer(BusinessTripBaseSerializer):
    pass


class TripPlanSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    users = UserSerializer(many=True, required=False)

    class Meta:
        model = TripPlan
        fields = [
            'id',
            'users',
            'text',
        ]


class TripExpenseSerializer(serializers.ModelSerializer):
    file = SelectItemField(model='document.File', extra_field=['id', 'url', 'size', 'file_size', 'name'],
                           required=False)
    type = SelectItemField(model='reference.ExpenseType', extra_field=['name'], required=False)

    class Meta:
        model = TripExpense
        fields = [
            'id',
            'amount',
            'comment',
            'date',
            'trip',
            'type',
            'file',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        amount = attrs.get('amount')
        type = attrs.get('type')
        trip = attrs.get('trip')

        if not amount:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='amount')
            raise ValidationError2(message)

        if not type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='type')
            raise ValidationError2(message)

        if not trip:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='trip id')
            raise ValidationError2(message)

        return attrs


class BusinessTripDetailSerializer(BusinessTripBaseSerializer):
    verifications = serializers.SerializerMethodField(read_only=True)
    expenses = TripExpenseSerializer(many=True, read_only=True)
    compose = serializers.SerializerMethodField(read_only=True)

    class Meta(BusinessTripBaseSerializer.Meta):
        fields = BusinessTripBaseSerializer.Meta.fields + ['verifications', 'compose', 'expenses']

    def get_verifications(self, obj):
        verifications = TripVerification.objects.filter(trip_id=obj.id).order_by('-is_sender', 'left_at', 'arrived_at')
        return TripBaseVerificationSerializer(verifications, many=True).data

    def get_data(self, name, object):
        return {
            'doc_type': name,
            'status': getattr(object.status, 'name', None),
            'url': getattr(object.file, 'url', None),
            'file_id': getattr(object.file, 'id', None),
            'extension': getattr(object.file, 'extension', None),
            'size': getattr(object.file, 'file_size', None),
            'name': getattr(object.file, 'name', None),
            'registered_document_id': object.registered_document_id,
            'curator': getattr(object.curator, 'full_name', None),
            'register_number': object.register_number,
            'register_date': object.register_date
        }

    def get_compose(self, obj):
        def determine_name(document_sub_type_id):
            if document_sub_type_id in [CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_SUB_TYPE,
                                        CONSTANTS.DOC_TYPE_ID.LOCAL_DECREE_SUB_TYPE,
                                        CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2]:
                return 'decree'
            elif document_sub_type_id == CONSTANTS.DOC_TYPE_ID.LOCAL_BUSINESS_TRIP_ORDER:
                return 'order'
            elif document_sub_type_id == CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_NOTICE_V2:
                return 'changed_notice'
            elif document_sub_type_id == CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2:
                return 'changed_decree'
            else:
                return 'notice'

        composed_data = []

        if obj.notice:
            name = determine_name(obj.notice.document_sub_type_id)
            data = self.get_data(name, obj.notice)
            composed_data.append(data)

        if obj.order:
            name = determine_name(obj.order.document_sub_type_id)
            data = self.get_data(name, obj.order)
            composed_data.append(data)

        extended_trip = (
            BusinessTrip.objects
            .filter(parent_id=obj.id)
            .select_related("notice", "order")
            .order_by("-created_date")
            .first()
        )

        if extended_trip:
            if extended_trip.notice and extended_trip.notice.file_id:
                name = determine_name(extended_trip.notice.document_sub_type_id)
                data = self.get_data(name, extended_trip.notice)
                composed_data.append(data)

            if extended_trip.order and extended_trip.order.file_id:
                name = determine_name(extended_trip.order.document_sub_type_id)
                data = self.get_data(name, extended_trip.order)
                composed_data.append(data)

        return composed_data


class TripPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripPlace
        fields = ['id', 'name', 'address', 'lat', 'lng', 'created_date']


class VisitedPlaceSerializer(serializers.ModelSerializer):
    place = SelectItemField(
        model='compose.TripPlace',
        extra_field=['name', 'id', 'address', 'lat', 'lng'],
        required=False
    )

    class Meta:
        model = VisitedPlace
        fields = [
            'id',
            'place',
            'trip_verification',
            'created_date',
        ]
        read_only_fields = ['created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        trip_verification = attrs.get('trip_verification')

        if not trip_verification:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='trip_verification')
            raise ValidationError2(message)

        if trip_verification.arrived_at and trip_verification.left_at:
            message = get_response_message(request, 700)
            raise ValidationError2(message)

        return attrs


class TripBaseVerificationSerializer(serializers.ModelSerializer):
    arrived_verified_by = SelectItemField(model='user.User',
                                          extra_field=['full_name', 'first_name', 'last_name', 'color', 'id',
                                                       'position', 'father_name'],
                                          required=False)
    left_verified_by = SelectItemField(model='user.User',
                                       extra_field=['full_name', 'first_name', 'last_name', 'color', 'id', 'position',
                                                    'father_name'],
                                       required=False)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    sender_company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    region = SelectItemField(model='reference.Region', extra_field=['id', 'name', 'name_uz', 'name_ru', 'country'],
                             required=False)
    visited_places = VisitedPlaceSerializer(many=True, required=False)

    class Meta:
        model = TripVerification
        fields = [
            'id',
            'is_sender',
            'verified',
            'arrived_verified_by',
            'left_verified_by',
            'arrived_at',
            'left_at',
            'company',
            'region',
            'next_destination_type',
            'next_destination_id',
            'visited_places',
            'arrived_lat',
            'arrived_lng',
            'arrived_address',
            'left_lat',
            'left_lng',
            'left_address',
            'sender_company',
        ]


class TripVerificationSerializer(TripBaseVerificationSerializer):
    trip = BusinessTripSerializer(required=False)

    class Meta(TripBaseVerificationSerializer.Meta):
        fields = TripBaseVerificationSerializer.Meta.fields + ['trip']


class RestoreTripVerificationSerializer(serializers.Serializer):
    decree_id = serializers.IntegerField(required=False)
    create_trip = serializers.BooleanField(required=False)


class UpdateTripVerificationSerializer(serializers.Serializer):
    regions = serializers.ListField(child=serializers.IntegerField(), required=False)
    end_date = serializers.DateField(required=True)
