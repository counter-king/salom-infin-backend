from django.db import transaction
from django.db.models import Value, F, Q
from django.db.models.functions import Coalesce
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework.generics import get_object_or_404

from apps.company.models import Company, Department
from apps.company.serializers import (
    CompanySerializer,
    DepartmentWithoutChildSerializer,
)
from apps.compose.models import (
    ComposeStatus,
    Compose,
    Approver,
    Signer,
    Receiver,
    ComposeVersionModel,
    Tag,
    BusinessTrip,
    ComposeLink, TripVerification,
)

from apps.compose.serializers.v1.compose.trips import (
    BusinessTripSerializer,
)
from apps.compose.tasks.delays import create_compose_version
from apps.compose.tasks.utils import add_object_id_to_trip
from apps.document.models import File
from apps.document.serializers import FileSerializer
from apps.reference.models import Correspondent, DocumentType, DocumentSubType, Journal, Region, Country
from apps.reference.serializers import CorrespondentSerializer
from apps.reference.tasks import action_log
from apps.user.models import TopSigner
from base_model.serializers import ContentTypeMixin
from config.middlewares.current_user import get_current_user_id
from utils.constant_ids import get_compose_status_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField, serialize_m2m
from utils.tools import get_or_none, clean_html, remove_all_whitespaces, get_user_ip


class ApproveListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    performers = serializers.JSONField(required=False, allow_null=True, write_only=True)
    resolution_text = serializers.CharField(required=False, allow_null=True, write_only=True)
    resolution_type = serializers.CharField(required=False, allow_null=True, write_only=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Approver
        fields = [
            'action_date',
            'comment',
            'deadline',
            'id',
            'is_approved',
            'user',
            'performers',
            'resolution_text',
            'resolution_type',
            'added_by'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        is_approved = attrs.get('is_approved')
        comment = attrs.get('comment')

        if is_approved is False and not comment:
            message = get_response_message(request, 607)
            raise ValidationError2(message)

        return attrs


class SignerListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    pkcs7 = serializers.CharField(required=False, max_length=100000000000000000,
                                  allow_null=True)
    company_region_name = serializers.SerializerMethodField()

    class Meta:
        model = Signer
        fields = [
            'action_date',
            'comment',
            'compose',
            'deadline',
            'id',
            'is_all_approved',
            'is_signed',
            'user',
            'pkcs7',
            'type',
            'performers',
            'resolution_text',
            'resolution_type',
            'company_region_name',
        ]

    def get_company_region_name(self, obj):
        try:
            return obj.user.company.region.name
        except AttributeError:
            return None

    def validate(self, attrs):
        request = self.context.get('request')
        is_signed = attrs.get('is_signed')
        comment = attrs.get('comment')

        if is_signed is False and not comment:
            message = get_response_message(request, 607)
            raise ValidationError2(message)

        return attrs


class TagSerializer(serializers.ModelSerializer):
    document_sub_type = SelectItemField(model='reference.DocumentSubType', extra_field=['name'], required=False)

    class Meta:
        model = Tag
        fields = ['id', 'name', 'name_uz', 'name_ru', 'document_sub_type']


class TagCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'name_uz', 'name_ru']

    def to_internal_value(self, data):
        return data.get('id')


class ComposeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComposeStatus
        fields = [
            'id',
            'is_approve',
            'is_default',
            'is_draft',
            'name',
            'name_uz',
            'name_ru',
        ]


class ReceiverSerializer(serializers.ModelSerializer):
    companies = CompanySerializer(many=True, required=False)
    departments = DepartmentWithoutChildSerializer(many=True, required=False)
    organizations = CorrespondentSerializer(many=True, required=False)

    class Meta:
        model = Receiver
        fields = [
            'companies',
            'departments',
            'id',
            'organizations',
            'type',
        ]


class ComposeLinkSerializer(serializers.ModelSerializer):
    from_compose = SelectItemField(model='compose.Compose',
                                   extra_field=['id', 'register_number',
                                                'status',
                                                'short_description',
                                                'registered_document',
                                                'content',
                                                'journal'],
                                   required=False)
    to_compose = SelectItemField(model='compose.Compose',
                                 extra_field=['id', 'register_number',
                                              'status',
                                              'short_description',
                                              'registered_document',
                                              'content',
                                              'journal'],
                                 required=False)

    class Meta:
        model = ComposeLink
        fields = [
            'created_date',
            'from_compose',
            'id',
            'modified_date',
            'to_compose',
            'link_type',
        ]


class ComposeListSerializer(serializers.ModelSerializer):
    status = SelectItemField(model='compose.ComposeStatus',
                             extra_field=['name', 'id', 'is_default', 'is_draft'],
                             read_only=True)
    parent = SelectItemField(model='compose.Compose',
                             extra_field=['id', 'register_number', 'register_date'],
                             required=False)
    approvers = ApproveListSerializer(many=True, read_only=True)
    signers = SignerListSerializer(many=True, read_only=True)
    author = SelectItemField(model='user.User',
                             extra_field=['full_name', 'first_name', 'last_name',
                                          'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                          'top_level_department', 'department', 'company', 'email'],
                             required=False)
    title = SelectItemField(model='reference.DocumentTitle',
                            extra_field=['id', 'name'], required=False)
    document_type = SelectItemField(model='reference.DocumentType',
                                    extra_field=['id', 'name'], required=False)
    document_sub_type = SelectItemField(model='reference.DocumentSubType',
                                        extra_field=['id', 'name'], required=False)

    class Meta:
        model = Compose
        fields = [
            'approvers',
            'author',
            'created_date',
            'document_sub_type',
            'document_sub_type',
            'document_type',
            'document_type',
            'id',
            'journal',
            'modified_date',
            'parent',
            'register_number',
            'short_description',
            'signers',
            'status',
            'title',
        ]


class ComposeVerifySerializer(serializers.ModelSerializer):
    approvers = serializers.SerializerMethodField(read_only=True)
    signers = serializers.SerializerMethodField(read_only=True)
    file = SelectItemField(model='document.File', extra_field=['url', 'file_size', 'size', 'name', 'id'],
                           required=False)
    author = SelectItemField(model='user.User',
                             extra_field=['full_name', 'first_name', 'last_name',
                                          'color', 'id', 'position', 'status',
                                          'top_level_department', 'department', 'company'],
                             required=False)

    class Meta:
        model = Compose
        fields = [
            'author',
            'approvers',
            'signers',
            'file',
            'created_date'
        ]

    def get_approvers(self, obj):
        data = []
        for item in obj.approvers.all():
            data.append({
                'id': item.id,
                'is_approved': item.is_approved,
                'user': item.user.full_name,
                'action_date': item.action_date,
                'position': item.user.position.name if item.user.position else None
            })

        return data

    def get_signers(self, obj):
        data = []
        for item in obj.signers.all():
            data.append({
                'id': item.id,
                'is_signed': item.is_signed,
                'user': item.user.full_name,
                'action_date': item.action_date,
                'certificate': item.certificate_info,
                'position': item.user.position.name if item.user.position else None
            })

        return data


class ComposeSerializer(ContentTypeMixin, serializers.ModelSerializer):
    author = SelectItemField(model='user.User',
                             extra_field=['full_name', 'first_name', 'last_name',
                                          'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                          'top_level_department', 'department', 'company', 'email'],
                             read_only=True)
    curator = SelectItemField(model='user.User',
                              extra_field=['full_name', 'first_name', 'last_name',
                                           'color', 'id', 'position', 'assistant'],
                              required=False)
    parent = SelectItemField(model='compose.Compose',
                             extra_field=['id', 'register_number', 'register_date'],
                             required=False)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'passport_seria',
                                        'top_level_department', 'position',
                                        'company', 'avatar',
                                        'passport_number', 'passport_issued_by', 'passport_issue_date'],
                           required=False)
    status = SelectItemField(model='compose.ComposeStatus',
                             extra_field=['name', 'id', 'is_default', 'is_draft'],
                             read_only=True)
    sender = SelectItemField(model='company.Department',
                             extra_field=['name', 'id'], required=False)
    title = SelectItemField(model='reference.DocumentTitle',
                            extra_field=['id', 'name'], required=False)
    document_type = SelectItemField(model='reference.DocumentType',
                                    extra_field=['id', 'name'], required=False)
    document_sub_type = SelectItemField(model='reference.DocumentSubType',
                                        extra_field=['id', 'name'], required=False)
    files = FileSerializer(many=True, required=False)
    approvers = ApproveListSerializer(many=True, required=False)
    signers = SignerListSerializer(many=True, required=False)
    organizations = serializers.ListField(required=False, write_only=True, child=serializers.IntegerField())
    departments = serializers.ListField(required=False, write_only=True, child=serializers.IntegerField())
    companies = serializers.ListField(required=False, write_only=True, child=serializers.IntegerField())
    receiver = ReceiverSerializer(required=False)
    tags = TagCreateSerializer(many=True, required=False)
    notices = BusinessTripSerializer(many=True, required=False)
    # trip_plans = TripPlanSerializer(many=True, required=False)
    # bookings = BookingSerializer(many=True, required=False)
    old_attorney_id = serializers.IntegerField(required=False, write_only=True, allow_null=True)

    class Meta:
        model = Compose
        fields = [
            'id',
            'approvers',
            'author',
            'companies',
            'company',
            'content',
            'content_type',
            'curator',
            'created_date',
            'departments',
            'document_type',
            'document_sub_type',
            'files',
            'journal',
            'notices',
            'modified_date',
            'organizations',
            'receiver',
            'register_date',
            'register_number',
            'registered_document',
            'replied_document',
            'sender',
            'short_description',
            'signers',
            'status',
            'title',
            'tags',
            # 'bookings',
            'trip_notice_id',
            # 'trip_plans',
            'parent',
            'user',
            'start_date',
            'end_date',
            'old_attorney_id',
            'additional_data',
        ]
        read_only_fields = [
            'author',
            'status',
            'receiver',
            'replied_document',
            'registered_document',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        # signers = attrs.get('signers')
        journal = attrs.get('journal')
        type = attrs.get('document_type')
        sub_type = attrs.get('document_sub_type')
        content = attrs.get('content')
        sender = attrs.get('sender')
        curator = attrs.get('curator')

        # if not signers:
        #     message = get_response_message(request, 605)
        #     raise ValidationError2(message)

        if not journal:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='journal')
            raise ValidationError2(message)

        if not Journal.objects.filter(id=journal.id, is_for_compose=True).exists():
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=f'journal {journal.name}')
            raise ValidationError2(message)

        if not type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='document_type')
            raise ValidationError2(message)

        if not DocumentType.objects.filter(id=type.id, is_for_compose=True).exists():
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=type.name)
            raise ValidationError2(message)

        if not sub_type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='document_sub_type')
            raise ValidationError2(message)

        if not DocumentSubType.objects.filter(document_type_id=type.id, id=sub_type.id,
                                              document_type__is_for_compose=True).exists():
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=sub_type.name)
            raise ValidationError2(message)

        if not content:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='content')
            raise ValidationError2(message)

        if not sender:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='sender')
            raise ValidationError2(message)

        # if type in CONSTANTS.COMPOSE.TYPES.NOTICE_LIST and not curator:
        #     message = get_response_message(request, 600)
        #     message['message'] = message['message'].format(type='curator')
        #     raise ValidationError2(message)

        if curator:
            get_or_none(TopSigner, request, user_id=curator.id)
            has_assistants = curator.assistants.filter(is_active=True).exists()
            if not has_assistants:
                message = get_response_message(request, 619)
                message['message'] = message['message'].format(curator=curator.full_name)
                raise ValidationError2(message)

        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Sort signers by is_signed (True first), then created_date
        signers = instance.signers.all().annotate(
            is_signed_bool=Coalesce('is_signed', Value(False))
        ).order_by(
            F('is_signed_bool').desc(nulls_last=True),
            'created_date'
        )
        data['signers'] = SignerListSerializer(signers, many=True).data

        # You can also do similar for 'approvers' if needed
        approvers = instance.approvers.all().order_by('created_date')
        data['approvers'] = ApproveListSerializer(approvers, many=True).data

        return data

    # def create(self, validated_data):
    #     request = self.context.get('request')
    #     files = validated_data.pop('files', [])
    #     approvers = validated_data.pop('approvers', [])
    #     signers = validated_data.pop('signers', [])
    #     organizations = validated_data.pop('organizations', [])
    #     departments = validated_data.pop('departments', [])
    #     companies = validated_data.pop('companies', [])
    #     tags = validated_data.pop('tags', [])
    #     notices = validated_data.pop('notices', [])
    #     # TODO: this is commented out because the bank wanted to remove for now
    #     # bookings = validated_data.pop('bookings', [])
    #     # trip_plans = validated_data.pop('trip_plans', [])
    #     trip_notice_id = validated_data.get('trip_notice_id', None)
    #     old_attorney_id = validated_data.pop('old_attorney_id', None)
    #     instance = Compose.objects.create(**validated_data)
    #
    #     # serialize many to many fields
    #     self._update_or_create_m2m_relationships('create', instance, files, tags)
    #
    #     # create who will receive the document
    #     data = {
    #         'companies': companies,
    #         'departments': departments,
    #         'organizations': organizations,
    #     }
    #     self._update_or_create_receiver(instance, data)
    #
    #     user = request.user
    #     instance.author_id = user.id
    #     instance.company_id = user.company_id
    #     instance.status_id = get_compose_status_id()
    #     instance.check_id = get_random_string(length=8, allowed_chars='1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    #     instance.parent_id = trip_notice_id
    #     instance.save()
    #
    #     # write activity log for created base document
    #     ct_id = self.get_content_type(instance)
    #     user_ip = get_user_ip(request)
    #     action_log.apply_async(
    #         (user.id, 'created', '100', ct_id,
    #          instance.id, user_ip, instance.register_number), countdown=2)
    #
    #     self._create_approvers(approvers, instance, request)
    #     self._create_signers(signers, approvers, instance, request)
    #     self._create_business_trip(notices, instance)
    #
    #     if instance.document_sub_type_id == 37:
    #         notices_data = self.initial_data.get('notices', [])
    #
    #         for notice in notices_data:
    #             parent_id = notice.get('parent')
    #             if hasattr(parent_id, 'id'):
    #                 parent_id = parent_id.id
    #             regions = notice.get('regions', [])
    #             end_date = notice.get('end_date')
    #
    #             if parent_id and isinstance(regions, list):
    #                 self._update_trip_verifications(parent_id, regions, end_date)
    #
    #     # self._create_bookings(bookings, instance)
    #     # self._create_trip_plans(trip_plans, instance)
    #     self._link_compose(instance.id, trip_notice_id)
    #     self._link_compose(instance.id, old_attorney_id)
    #
    #     # add instance id to trip notice id
    #     if instance.document_sub_type_id in [CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
    #                                          CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2,
    #                                          CONSTANTS.DOC_TYPE_ID.BUSINESS_TRIP_DECREE_FOREIGN]:
    #         add_object_id_to_trip.apply_async((trip_notice_id, instance.id), countdown=2)
    #
    #     return instance

    def create(self, validated_data):
        request = self.context.get("request")

        files = validated_data.pop('files', [])
        approvers = validated_data.pop('approvers', [])
        signers = validated_data.pop('signers', [])
        organizations = validated_data.pop('organizations', [])
        departments = validated_data.pop('departments', [])
        companies = validated_data.pop('companies', [])
        tags = validated_data.pop('tags', [])
        notices = validated_data.pop('notices', [])
        trip_notice_id = validated_data.get('trip_notice_id')
        old_attorney_id = validated_data.pop('old_attorney_id', None)
        additional_data = validated_data.pop('additional_data', None)

        user = request.user

        with transaction.atomic():
            instance = Compose.objects.create(**validated_data)

            # set system fields
            instance.author_id = user.id
            instance.company_id = user.company_id
            instance.status_id = get_compose_status_id()
            instance.check_id = get_random_string(
                length=8,
                allowed_chars='1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
            instance.parent_id = trip_notice_id
            instance.save()

            # m2m
            self._update_or_create_m2m_relationships('create', instance, files, tags)

            # receivers
            receiver_data = {
                'companies': companies,
                'departments': departments,
                'organizations': organizations,
            }
            self._update_or_create_receiver(instance, receiver_data)

            # workflow
            self._create_approvers(approvers, instance, request)
            self._create_signers(signers, approvers, instance, request)
            self._create_business_trip(notices, instance)

            # special case
            self._handle_subtype_specifics(instance, notices, additional_data)

            # link
            self._link_compose(instance.id, trip_notice_id)
            self._link_compose(instance.id, old_attorney_id)

        # OUTSIDE transaction → async stuff
        self._log_create_action(request, instance, user)
        self._maybe_add_to_trip(instance, trip_notice_id)

        return instance

    def _log_create_action(self, request, instance, user):
        ct_id = self.get_content_type(instance)
        user_ip = get_user_ip(request)

        def _send():
            action_log.apply_async(
                (user.id, 'created', '100', ct_id, instance.id, user_ip, instance.register_number),
                countdown=2,
            )

        transaction.on_commit(_send)

    def _maybe_add_to_trip(self, instance, trip_notice_id):
        if instance.document_sub_type_id in [
            CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
            CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2,
            CONSTANTS.DOC_TYPE_ID.BUSINESS_TRIP_DECREE_FOREIGN,
        ] and trip_notice_id:
            def _send():
                add_object_id_to_trip.apply_async((trip_notice_id, instance.id), countdown=2)

            transaction.on_commit(_send)

    def _handle_subtype_specifics(self, instance, notices=None, specs_data=None):
        """
        Run extra logic per document_sub_type_id.
        - notices: already validated list of notices
        - specs_data: arbitrary json for other subtypes
        """
        doc_subtype = instance.document_sub_type_id

        if doc_subtype == 37:
            self._handle_subtype_37(instance, notices or [])
            return

        if doc_subtype == 39:
            self._handle_subtype_39(instance, specs_data or {})
            return

    def _handle_subtype_37(self, instance, notices: list[dict]):
        """
        Example input for a notice:
        {
            "parent": 123 or {"id": 123},
            "regions": [1, 2, 3],
            "end_date": "2025-11-02"
        }
        """
        for notice in notices:
            parent_id = notice.get("parent")
            # sometimes FE sends obj, sometimes id:
            if hasattr(parent_id, "id"):
                parent_id = parent_id.id

            regions = notice.get("regions") or []
            end_date = notice.get("end_date")

            if parent_id and isinstance(regions, list):
                self._update_trip_verifications(parent_id, regions, end_date)

    def _handle_subtype_39(self, instance, specs_data: dict):
        # TODO: 39 is Explanation Letter Sub Type, Need to handle specific cases
        pass

    def _link_compose(self, from_compose_id, to_compose_id):
        if to_compose_id:
            ComposeLink.objects.create(
                from_compose_id=from_compose_id,
                to_compose_id=to_compose_id)

    def _create_business_trip(self, notices, instance):
        for notice in notices:
            destinations = notice.pop('companies', [])
            regions = notice.pop('regions', [])
            countries = notice.pop('countries', [])
            tags = notice.pop('tags', [])
            trip_data = BusinessTrip.objects.create(notice_id=instance.id, **notice)
            serialize_m2m('create', Region, 'locations', regions, trip_data)
            serialize_m2m('create', Country, 'countries', countries, trip_data)
            serialize_m2m('create', Company, 'destinations', destinations, trip_data)
            self._update_or_create_m2m_relationships('create', trip_data, [], tags)

    # def _create_bookings(self, bookings, instance):
    #     for booking in bookings:
    #         passengers = booking.pop('passengers', [])
    #         segments = booking.pop('segments', [])
    #         booking_data = Booking.objects.create(compose=instance, **booking)
    #         self._create_booking_data(booking_data, passengers, segments)

    # def _create_booking_data(self, booking, passengers, segments):
    #     for passenger in passengers:
    #         Passenger.objects.create(booking=booking, **passenger)
    #
    #     for segment in segments:
    #         BookingSegment.objects.create(booking=booking, **segment)

    # def _create_trip_plans(self, trip_plans, instance):
    #     for trip_plan in trip_plans:
    #         users = trip_plan.pop('users', [])
    #         trip_plan_data = TripPlan.objects.create(compose=instance, **trip_plan)
    #         serialize_m2m('create', User, 'users', users, trip_plan_data)

    def _create_approvers(self, approvers, instance, request):
        user_ip = get_user_ip(request)
        user_id = request.user.id
        ct_id = self.get_content_type(instance)
        compose_id = instance.id
        buffer = []
        for approver in approvers:
            buffer.append(Approver(
                compose=instance,
                **approver
            ))
            # Approver.objects.create(compose=instance, **approver)
            user = approver.get('user')
            action_log.apply_async((user_id, 'created', '124', ct_id,
                                    compose_id, user_ip, user.full_name), countdown=2)

        if buffer:
            Approver.objects.bulk_create(buffer)
            buffer.clear()

    def _create_signers(self, signers, approvers, instance, request):
        user_ip = get_user_ip(request)
        user_id = request.user.id
        ct_id = self.get_content_type(instance)
        compose_id = instance.id
        buffer = []
        for signer in signers:
            is_all_approved = True if not approvers else None
            buffer.append(Signer(
                compose=instance,
                is_all_approved=is_all_approved,
                **signer
            ))
            # Signer.objects.create(compose=instance, is_all_approved=is_all_approved, **signer)
            user = signer.get('user')
            action_log.apply_async((user_id, 'created', '123', ct_id,
                                    compose_id, user_ip, user.full_name), countdown=2)

        if buffer:
            Signer.objects.bulk_create(buffer)
            buffer.clear()

    def _update_or_create_m2m_relationships(self, action, instance, files, tags):
        if files:
            serialize_m2m(action, File, 'files', files, instance)
        if tags:
            serialize_m2m(action, Tag, 'tags', tags, instance)

    def _update_or_create_receiver(self, instance, related_data):
        receiver = None
        if related_data['departments'] and not related_data['companies']:
            receiver = self._get_or_create_receiver(instance, type=CONSTANTS.COMPOSE.RECEIVERS.DEPARTMENTS)
            serialize_m2m('update', Department, 'departments', related_data['departments'], receiver)

        if related_data['companies'] and not related_data['departments']:
            receiver = self._get_or_create_receiver(instance, type=CONSTANTS.COMPOSE.RECEIVERS.COMPANIES)
            serialize_m2m('update', Company, 'companies', related_data['companies'], receiver)

        if related_data['organizations'] and not related_data['companies'] and not related_data['departments']:
            receiver = self._get_or_create_receiver(instance, type=CONSTANTS.COMPOSE.RECEIVERS.ORGANIZATIONS)
            serialize_m2m('update', Correspondent, 'organizations', related_data['organizations'], receiver)

        if receiver:
            instance.receiver = receiver
            instance.save()

    def _get_or_create_receiver(self, instance, type=CONSTANTS.COMPOSE.RECEIVERS.DEPARTMENTS):
        return get_or_none(Receiver, with_none=True, id=instance.receiver_id) or Receiver.objects.create(type=type)

    def _update_trip_verifications(self, trip_id, region_ids, end_date=None):
        trip = get_object_or_404(BusinessTrip, id=trip_id)

        if end_date:
            trip.end_date = end_date
        trip.is_active = False
        trip.save()

        existing_verifications = TripVerification.objects.filter(trip=trip)
        existing_region_ids = set()
        to_delete = []

        for v in existing_verifications:
            if v.is_sender or (v.region and v.region.id in region_ids):
                existing_region_ids.add(v.region.id)
            elif not v.arrived_at and not v.left_at:
                to_delete.append(v)

        for v in to_delete:
            v.delete()

        for region_id in region_ids:
            if region_id not in existing_region_ids:
                region = get_object_or_404(Region, id=region_id)
                TripVerification.objects.create(trip=trip, region=region)

    def update(self, instance, validated_data):
        # Pop related data from validated_data
        related_data = {
            'files': validated_data.pop('files', []),
            'approvers': validated_data.pop('approvers', []),
            'signers': validated_data.pop('signers', []),
            'organizations': validated_data.pop('organizations', []),
            'departments': validated_data.pop('departments', []),
            'companies': validated_data.pop('companies', []),
            'notices': validated_data.pop('notices', []),
            # 'bookings': validated_data.pop('bookings', []),
            # 'trip_plans': validated_data.pop('trip_plans', []),
            'tags': validated_data.pop('tags', []),
        }

        old_text = instance.content
        new_text = validated_data.get('content')
        old_curator = instance.curator
        new_curator = validated_data.get('curator')

        # Update the instance with validated data
        instance = super(ComposeSerializer, self).update(instance, validated_data)

        # Call your helper function with signers from related_data
        self._manage_signers_and_added_approvers(instance, related_data['signers'])

        # Handle M2M relationships for files and tags
        self._update_or_create_m2m_relationships('update', instance, related_data['files'], related_data['tags'])

        # Handle receiver-specific M2M updates
        self._update_or_create_receiver(instance, related_data)

        # Handle trip notices
        self._update_trip_notices(related_data['notices'], instance)

        # Handle bookings
        # self._update_bookings(related_data['bookings'], instance)

        # Handle trip plans
        # self._update_trip_plans(related_data['trip_plans'], instance)

        # Handle approvers and signers updates
        text_changed = self.has_not_been_changed(old_text, new_text)
        self._update_approvers_and_signers(instance, not text_changed,
                                           related_data['approvers'],
                                           related_data['signers'])

        # Handle text changes and status updates
        if not text_changed:
            self._create_history_and_update_status(instance, old_text, new_text)
        else:
            if new_curator and old_curator and new_curator.id != old_curator.id:
                # Check if the old curator and his assistants are created
                # If so delete them
                self.remove_curator_and_assistant(instance, old_curator,
                                                  create_assistant=True, new_curator=new_curator)

        return instance

    def _create_history_and_update_status(self, instance, old_text, new_text):
        old_text = clean_html(old_text)
        new_text = clean_html(new_text)
        user_id = get_current_user_id()

        # Save difference of contents
        create_compose_version.apply_async((instance.id, old_text, new_text, user_id))

        # Reset the status of the compose model
        instance.status_id = ComposeStatus.objects.get(is_default=True).id
        instance.save()

    def _update_approvers_and_signers(self, instance, text_changed, approvers, signers):
        current_approvers = {approver.user_id for approver in instance.approvers.all()}
        new_approvers = [
            obj for obj in approvers
            if obj.get('user') and obj.get('user').id not in current_approvers
        ]

        self.update_approvers(approvers, text_changed=text_changed)
        update_signers_kwargs = {
            'new_approver_added': bool(new_approvers),
            'exist_approvers': len(approvers) > 0,
            'text_changed': text_changed
        }
        self.update_signers(signers, **update_signers_kwargs)

    def _manage_signers_and_added_approvers(self, instance, new_signers_data):
        # Get existing signer user IDs from DB
        existing_signers = Signer.objects.filter(compose=instance)
        existing_user_ids = set(existing_signers.values_list('user_id', flat=True))

        # Get new signer user IDs from incoming data
        new_user_ids = set(
            self._get_user_id(signer.get('user'))
            for signer in new_signers_data
        )

        # Find which users were removed
        removed_user_ids = existing_user_ids - new_user_ids

        # Delete removed signers and their related approvers
        if removed_user_ids:
            Approver.objects.filter(compose=instance, added_by_id__in=removed_user_ids).delete()

    def _get_user_id(self, user):
        if isinstance(user, dict):
            return user.get('id')
        elif hasattr(user, 'id'):
            return user.id
        return user  # fallback if it's already an ID

    def has_not_been_changed(self, old_text: str, new_text: str) -> bool:
        clean_old_text = clean_html(old_text)
        clean_new_text = clean_html(new_text)

        return remove_all_whitespaces(clean_old_text) == remove_all_whitespaces(clean_new_text)

    def check_errors(self, model, user=None):
        request = self.context.get('request')
        instance = self.instance

        if not user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)

        # if model.objects.filter(compose=instance, user=user).exists():
        #     message = get_response_message(request, 602)
        #     message['message'] = message['message'].format(object=user.full_name)
        #     raise ValidationError2(message)

    def update_approvers(self, approvers: list, text_changed=False):
        request = self.context.get('request')
        approver_items = dict((i.user_id, i) for i in self.instance.approvers.all())  # Use user_id as the key
        compose_id = self.instance.id
        user_id = request.user.id
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(self.instance)
        to_create = []
        for item in approvers:
            user = item.get('user')

            if not user:
                raise ValidationError2({"message": "User must be provided for each signer."})

            if user.id in approver_items:
                # If the user exists in the current approvers, update the record
                approver_by_item = approver_items.pop(user.id)
                if text_changed:
                    approver_by_item.is_approved = None
                approver_by_item.save()
            else:
                # If the user does not exist, create a new approver
                self.check_errors(Approver, user)
                to_create.append(Approver(compose=self.instance, **item))
                # Approver.objects.create(compose=self.instance, **item)
                action_log.apply_async(
                    (user_id, 'created', '124', ct_id,
                     compose_id, user_ip, user.full_name), countdown=2)

        if to_create:
            Approver.objects.bulk_create(to_create)
            to_create.clear()

        # Delete any remaining approvers not included in the update
        self.remove_remaining_users(approver_items, request, '126')

    def update_signers(self, signers: list,
                       new_approver_added=False,
                       text_changed=False, exist_approvers=False):
        request = self.context.get('request')
        # Use user_id as the key
        existing_signers = {signer.user_id: signer for signer in self.instance.signers.all()}

        # Loop through provided signers to update or create records
        for signer_data in signers:
            user = signer_data.get('user')
            if not user:
                raise ValidationError2({"message": "User must be provided for each signer."})

            # Update existing signers
            if user.id in existing_signers:
                signer_record = existing_signers.pop(user.id)
                self.update_existing_signer(signer_record, text_changed)
            else:
                # Create new signer
                self.create_new_signer(user, signer_data, text_changed, request)

        # Remove signers not in the provided list
        self.remove_remaining_users(existing_signers, request, '125')

    def update_existing_signer(self, signer_record, text_changed):
        # Recompute purely from the current approvers in DB
        has_pending = self.instance.approvers.filter(
            Q(is_approved=False) | Q(is_approved__isnull=True)
        ).exists()
        signer_record.is_all_approved = not has_pending

        if text_changed and has_pending:
            signer_record.is_signed = None
            signer_record.is_all_approved = None  # reset visibility whenever text changes
            if self.instance.curator_id:
                self.remove_curator_and_assistant(self.instance, self.instance.curator)

        signer_record.save()

    def create_new_signer(self, user, signer_data, text_changed, request):
        """
        Creates a new signer record.
        - if the document text changed: reset both flags to None.
        - otherwise, compute is_all_approved from pending approvers.
        """
        signer_data = signer_data.copy()
        signer_data.pop('user', None)
        self.check_errors(Signer, user)

        if text_changed:
            Signer.objects.create(
                compose=self.instance,
                user=user,
                is_signed=None,
                is_all_approved=None,
                **signer_data
            )
        else:
            has_pending = self.instance.approvers.filter(
                Q(is_approved=False) | Q(is_approved__isnull=True)
            ).exists()
            Signer.objects.create(
                compose=self.instance,
                user=user,
                is_all_approved=not has_pending,
                **signer_data
            )
        user_id = request.user.id
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(self.instance)
        action_log.apply_async(
            (user_id, 'created', '123', ct_id,
             self.instance.id, user_ip, user.full_name), countdown=2)

    def remove_remaining_users(self, remaining_signers, request, desc_code):
        """
        Deletes any signers not included in the updated list.
        """
        user_id = request.user.id
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(self.instance)
        for signer in remaining_signers.values():
            user_name = signer.user.full_name
            signer.delete()
            action_log.apply_async(
                (user_id, 'deleted', desc_code, ct_id,
                 self.instance.id, user_ip, user_name), countdown=2)

    def remove_curator_and_assistant(self, instance, old_curator,
                                     create_assistant=False, new_curator=None):
        """
        If the document has been changed,
        the curator and assistant will be removed.
        And the document will be sent to the approvers and signers again.
        """

        # Remove the curator from signers
        Signer.objects.filter(compose_id=instance.id,
                              user_id=old_curator.id,
                              type='basic_signer').delete()

        # Get active assistants of the curator
        assistant_ids = list(old_curator.assistants.
                             filter(is_active=True).
                             values_list('assistant_id', flat=True))

        # Remove assistants from approvers
        Approver.objects.filter(compose_id=instance.id,
                                user_id__in=assistant_ids).delete()

        if create_assistant:
            self.create_assistant(instance, new_curator)

    def create_assistant(self, instance, new_curator):
        signers = instance.signers.all()
        all_signed = all(signer.is_signed for signer in signers)

        if all_signed:
            assistant_id = list(instance.curator.assistants.
                                filter(is_active=True).
                                values_list('assistant_id', flat=True))[0]
            # If all signers are signed, create a new assistant
            Approver.objects.create(
                compose=instance,
                user_id=assistant_id,
            )

    def _update_trip_notices(self, notices: list, instance):
        # Get all notice items for the given instance
        notice_items = {i.id: i for i in instance.notices.all()}

        for item in notices:
            if 'id' in item:
                # Update an existing notice
                notice_item = notice_items.pop(item['id'])
                destinations = item.pop('companies', [])
                locations = item.pop('regions', [])
                countries = item.pop('countries', [])
                tags = item.pop('tags', [])

                notice_item.start_date = item.get('start_date')
                notice_item.end_date = item.get('end_date')
                notice_item.user_id = item.get('user')
                notice_item.group_id = item.get('group_id')
                notice_item.save()
                # Handle Many-to-Many relationships and bookings
                serialize_m2m('update', Company, 'destinations', destinations, notice_item)
                serialize_m2m('update', Region, 'locations', locations, notice_item)
                serialize_m2m('update', Country, 'countries', countries, notice_item)
                self._update_or_create_m2m_relationships('update', notice_item, [], tags)
            else:
                # Create a new notice
                destinations = item.pop('companies', [])
                locations = item.pop('regions', [])
                countries = item.pop('countries', [])
                tags = item.pop('tags', [])

                # Check if a BusinessTrip with notice_id == instance.id exists
                existing_business_trip = BusinessTrip.objects.filter(notice_id=instance.id).first()

                if existing_business_trip:
                    # If it exists, use its order_id to create a new BusinessTrip
                    order_id = existing_business_trip.order_id
                    notice_data = BusinessTrip.objects.create(
                        notice=instance,
                        order_id=order_id,  # Use the existing order_id
                        **item
                    )
                else:
                    # If no existing BusinessTrip, create a new BusinessTrip without order_id
                    notice_data = BusinessTrip.objects.create(notice=instance, **item)
                serialize_m2m('create', Company, 'destinations', destinations, notice_data)
                serialize_m2m('create', Region, 'locations', locations, notice_data)
                serialize_m2m('create', Country, 'countries', countries, notice_data)
                self._update_or_create_m2m_relationships('create', notice_data, [], tags)

        # Delete notices not included in the update
        for remaining_notice in notice_items.values():
            remaining_notice.delete()

    # def _update_bookings(self, bookings, instance):
    #     # Get all booking items for the given notice
    #     booking_items = {i.id: i for i in instance.bookings.all()}
    #     for item in bookings:
    #         if 'id' in item:
    #             # Update an existing booking
    #             booking_item = booking_items.pop(item['id'])
    #
    #             passengers = item.pop('passengers', [])
    #             segments = item.pop('segments', [])
    #
    #             booking_item.type = item.get('type')
    #             booking_item.route = item.get('route')
    #             booking_item.save()
    #
    #             # Update segments and passengers
    #             self._update_booking_data(booking_item, passengers, segments)
    #
    #         else:
    #             # Create a new booking
    #             passengers = item.pop('passengers', [])
    #             segments = item.pop('segments', [])
    #             booking_data = Booking.objects.create(compose=instance, **item)
    #             self._update_booking_data(booking_data, passengers, segments)
    #
    #     # Delete bookings not included in the update
    #     for remaining_booking in booking_items.values():
    #         remaining_booking.delete()

    # def _update_booking_data(self, booking, passengers, segments):
    #     # Get all passenger items for the given booking
    #     passenger_items = {i.id: i for i in booking.passengers.all()}
    #     for item in passengers:
    #         if 'id' in item:
    #             # Update an existing passenger
    #             passenger_item = passenger_items.pop(item['id'])
    #             passenger_item.user = item.get('user')
    #             passenger_item.save()
    #         else:
    #             # Create a new passenger
    #             Passenger.objects.create(booking=booking, **item)
    #
    #     # Delete passengers not included in the update
    #     for remaining_passenger in passenger_items.values():
    #         remaining_passenger.delete()
    #
    #     # Get all segment items for the given booking
    #     segment_items = {i.id: i for i in booking.segments.all()}
    #     for item in segments:
    #         if 'id' in item:
    #             # Update an existing segment
    #             segment_item = segment_items.pop(item['id'])
    #             segment_item.departure_city = item.get('departure_city')
    #             segment_item.arrival_city = item.get('arrival_city')
    #             segment_item.departure_date = item.get('departure_date')
    #             segment_item.departure_end_date = item.get('departure_end_date')
    #             segment_item.arrival_date = item.get('arrival_date')
    #             segment_item.segment_class = item.get('segment_class')
    #             segment_item.save()
    #         else:
    #             # Create a new segment
    #             BookingSegment.objects.create(booking=booking, **item)
    #
    #     # Delete segments not included in the update
    #     for remaining_segment in segment_items.values():
    #         remaining_segment.delete()

    # def _update_trip_plans(self, trip_plans, instance):
    #     # Get all trip plan items for the given instance
    #     trip_plan_items = {i.id: i for i in instance.trip_plans.all()}
    #
    #     for item in trip_plans:
    #         if 'id' in item:
    #             # Update an existing trip plan
    #             trip_plan_item = trip_plan_items.pop(item['id'])
    #             users = item.pop('users', [])
    #             trip_plan_item.text = item.get('text')
    #             trip_plan_item.user = item.get('user')
    #             trip_plan_item.save()
    #             # Handle Many-to-Many relationships
    #             serialize_m2m('update', User, 'users', users, trip_plan_item)
    #         else:
    #             # Create a new trip plan
    #             users = item.pop('users', [])
    #             trip_data = TripPlan.objects.create(compose=instance, **item)
    #             serialize_m2m('create', User, 'users', users, trip_data)
    #
    #     # Delete trip plans not included in the update
    #     for remaining_trip_plan in trip_plan_items.values():
    #         remaining_trip_plan.delete()


class ComposeVersionSerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)

    class Meta:
        model = ComposeVersionModel
        fields = ['id', 'created_date', 'new_text', 'old_text', 'created_by']


class ComposeCustomUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Compose
        fields = ['content']
        read_only_fields = ['id']


class ApproveSerializer(serializers.ModelSerializer):
    compose = ComposeListSerializer(read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)

    class Meta:
        model = Approver
        fields = [
            'action_date',
            'comment',
            'compose',
            'id',
            'is_approved',
            'user',
        ]

    # def to_representation(self, instance):
    #     data = super(ApproveSerializer, self).to_representation(instance)
    #     compose = instance.compose
    #     compose = ComposeListSerializer(compose).data
    #
    #     data['compose'] = compose
    #
    #     return data


class ApproveDetailSerializer(serializers.ModelSerializer):
    compose = serializers.PrimaryKeyRelatedField(queryset=Compose.objects.all(), required=False)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)

    class Meta:
        model = Approver
        fields = [
            'action_date',
            'comment',
            'compose',
            'id',
            'is_approved',
            'user',
        ]

    def to_representation(self, instance):
        data = super(ApproveDetailSerializer, self).to_representation(instance)
        compose = instance.compose
        compose = ComposeSerializer(compose).data

        data['compose'] = compose

        return data


class SignerList2Serializer(serializers.ModelSerializer):
    compose = ComposeListSerializer(read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)

    class Meta:
        model = Signer
        fields = [
            'id',
            'action_date',
            'comment',
            'compose',
            'deadline',
            'is_all_approved',
            'is_signed',
            'user',
            'type',
        ]


class SignerDetailSerializer(serializers.ModelSerializer):
    compose = ComposeSerializer(read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    added_by = SelectItemField(model='user.User',
                               extra_field=['full_name', 'first_name', 'last_name',
                                            'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                            'top_level_department', 'department', 'company', 'email'],
                               required=False)

    class Meta:
        model = Signer
        fields = [
            'action_date',
            'comment',
            'compose',
            'deadline',
            'id',
            'is_all_approved',
            'is_signed',
            'user',
            'type',
            'performers',
            'resolution_text',
            'resolution_type',
            'added_by',
        ]
