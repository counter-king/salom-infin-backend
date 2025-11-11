from django.db.models import Q
from rest_framework import serializers

from apps.reference.models import (
    ActionModel,
    CommentModel,
    Correspondent,
    CityDistance,
    Country,
    DeliveryType,
    District,
    DocumentSubType,
    DocumentTitle,
    DocumentType,
    EmployeeGroup,
    ExpenseType,
    Journal,
    LanguageModel,
    Priority,
    Region,
    ShortDescription,
    StatusModel,
    AppVersion,
    AttendanceReason, ExceptionEmployee,
)
from apps.reference.tasks import action_log
from apps.user.models import User
from base_model.serializers import ContentTypeMixin
from config.middlewares.current_user import get_current_user_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import serialize_m2m, SelectItemField
from utils.tools import get_user_ip


class RecursiveSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class CommentSerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model="user.User",
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    file = SelectItemField(model="document.File",
                           extra_field=['id', 'name', 'url'], required=False)
    replies = RecursiveSerializer(many=True, read_only=True)
    edit = serializers.BooleanField(default=False, read_only=True)
    reply = serializers.BooleanField(default=False, read_only=True)

    class Meta:
        model = CommentModel
        fields = [
            'content_type',
            'created_by',
            'created_date',
            'description',
            'edit',
            'file',
            'id',
            'is_edited',
            'modified_date',
            'object_id',
            'replied_to',
            'replies',
            'reply'
        ]
        read_only_fields = ['created_date', 'is_edited', 'modified_date', 'is_deleted']

    def update(self, instance, validated_data):
        old_text = instance.description
        new_text = validated_data.get('description', instance.description)
        if old_text != new_text:
            instance.is_edited = True
        instance.description = new_text
        super().update(instance, validated_data)
        instance.save()
        return instance


class StatusModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusModel
        fields = ['id', 'name', 'name_uz', 'name_ru', 'name_en', 'description', 'group', 'is_default', 'created_date',
                  'is_active']


class CorrespondentSerializer(ContentTypeMixin, serializers.ModelSerializer):
    type = serializers.CharField(max_length=20, required=False)
    pinfl = serializers.CharField(max_length=14, required=False, allow_null=True, allow_blank=True)
    tin = serializers.CharField(max_length=15, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Correspondent
        fields = [
            'address',
            'birth_date',
            'checkpoint',
            'content_type',
            'description',
            'email',
            'father_name',
            'first_name',
            'gender',
            'id',
            'last_name',
            'legal_address',
            'legal_name',
            'name',
            'phone',
            'tin',
            'pinfl',
            'type',
        ]

    def validate(self, attrs):
        type = attrs.get('type')
        tin = attrs.get('tin', None)
        pinfl = attrs.get('pinfl', None)
        request = self.context.get('request')
        required_fields = {
            "legal": ["name", "tin", "legal_name", "legal_address", "phone"],
            "physical": ["first_name", "last_name", "father_name", "phone", "address", "gender"],
            "entrepreneur": ["name", "first_name", "last_name", "father_name", "phone", "address", "description",
                             "pinfl"]
        }

        if request.method.lower() not in ['put', 'patch']:
            if tin:
                qs = Correspondent.objects.filter(tin=tin).exists()
                if qs:
                    message = get_response_message(request, 602)
                    message['message'] = message['message'].format(object=f'INN: {tin}')
                    raise ValidationError2(message)

            if pinfl:
                qs = Correspondent.objects.filter(pinfl=pinfl).exists()
                if qs:
                    message = get_response_message(request, 602)
                    message['message'] = message['message'].format(object=f'PINFL: {pinfl}')
                    raise ValidationError2(message)

        if type not in required_fields:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='type')
            raise ValidationError2(message)

        for req_field in required_fields.get(type, []):
            if not attrs.get(req_field):
                request = self.context.get('request')
                message = get_response_message(request, 601)
                message['message'] = message['message'].format(req_field=req_field, type=type)
                raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        type = validated_data.get('type')
        first_name = validated_data.get('first_name', None)
        last_name = validated_data.get('last_name', None)
        father_name = validated_data.get('father_name', None)
        instance = Correspondent.objects.create(**validated_data)

        if type == CONSTANTS.CORRESPONDENTS.TYPES.PHYSICAL:
            if father_name:
                instance.name = f'{last_name} {first_name} {father_name}'
            else:
                instance.name = f'{last_name} {first_name}'
            instance.save()

        # write activity log for created correspondent
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(instance)
        action_log.apply_async(
            (user_id, 'created', '119', ct_id,
             instance.id, user_ip, instance.name), countdown=2)

        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        old_name = instance.name
        instance = super(CorrespondentSerializer, self).update(instance, validated_data)

        # write activity log for updated correspondent
        if old_name != instance.name:
            user_id = get_current_user_id()
            user_ip = get_user_ip(request)
            ct_id = self.get_content_type(instance)
            action_log.apply_async(
                (user_id, 'updated', '120', ct_id,
                 instance.id, user_ip, instance.name, old_name), countdown=2)

        return instance


class EmployeeGroupSerializer(ContentTypeMixin, serializers.ModelSerializer):
    from apps.user.serializers import UserSerializer
    employees = UserSerializer(many=True)

    class Meta:
        model = EmployeeGroup
        fields = ['id', 'name', 'employees', 'created_date', 'content_type']

    def create(self, validated_data):
        employees = validated_data.pop('employees', [])
        request = self.context.get('request')
        instance = EmployeeGroup.objects.create(**validated_data)
        serialize_m2m('create', User, 'employees', employees, instance)
        instance.save()

        # write activity log for created employee group
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(instance)
        action_log.apply_async(
            (user_id, 'created', '121', ct_id,
             instance.id, user_ip, instance.name), countdown=2)

        return instance

    def update(self, instance, validated_data):
        employees = validated_data.pop('employees', [])
        old_name = instance.name
        request = self.context.get('request')
        serialize_m2m('update', User, 'employees', employees, instance)
        instance = super(EmployeeGroupSerializer, self).update(instance, validated_data)

        # write activity log for updated employee group
        if old_name != instance.name:
            user_id = get_current_user_id()
            user_ip = get_user_ip(request)
            ct_id = self.get_content_type(instance)
            action_log.apply_async(
                (user_id, 'updated', '122', ct_id,
                 instance.id, user_ip, instance.name, old_name), countdown=2)

        return instance


class ShortDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortDescription
        fields = ['id', 'title', 'description', 'description_uz', 'description_ru', 'created_date']


class ActionModelSerializer(serializers.ModelSerializer):
    from apps.user.serializers import UserSerializer
    created_by = UserSerializer(read_only=True)
    description = SelectItemField(model='reference.ActionDescription',
                                  extra_field=['code', 'description', 'icon_name', 'color'],
                                  read_only=True)

    class Meta:
        model = ActionModel
        fields = [
            'action',
            'cause_of_deletion',
            'created_by',
            'created_date',
            'content_type',
            'description',
            'id',
            'ip_addr',
            'new_value',
            'object_id',
            'old_value',
        ]


class JournalSerializer(serializers.ModelSerializer):
    icon = SelectItemField(model='document.File', extra_field=['id', 'name', 'size'], required=False)

    class Meta:
        model = Journal
        fields = [
            'code',
            'created_date',
            'icon',
            'id',
            'index',
            'is_active',
            'is_auto_numbered',
            'is_for_compose',
            'name',
            'name_ru',
            'name_uz',
            'number_of_chars',
            'period_of_time',
            'prefix',
            'sort_order',
        ]
        read_only_fields = ['sort_order', 'is_active']

    def validate(self, attrs):
        request = self.context.get('request')
        code = attrs.get('code')
        prefix = attrs.get('prefix')
        instance = self.instance

        if instance is not None:
            if instance.code == code:
                pass

            if instance.prefix == prefix:
                pass

            return attrs

        if Journal.objects.filter(code=code).exists():
            msg = get_response_message(request, 602)
            msg['message'] = msg['message'].format(object=f'Kod: {code}')
            raise ValidationError2(msg)

        if Journal.objects.filter(prefix=prefix).exists():
            msg = get_response_message(request, 602)
            msg['message'] = msg['message'].format(object=prefix)
            raise ValidationError2(msg)

        return attrs

    def create(self, validated_data):
        count = Journal.objects.count()
        instance = Journal.objects.create(**validated_data)
        instance.sort_order = count + 1
        instance.save()
        return instance


class JournalChangeSortingSerializer(serializers.Serializer):
    sort_order = serializers.IntegerField(required=False)

    def validate(self, attrs):
        request = self.context.get('request')
        sort_order = attrs.get('sort_order')

        if sort_order is None:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='sort_order')
            raise ValidationError2(msg)

        return attrs


class JournalActivateOrDeactivateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        request = self.context.get('request')
        is_active = attrs.get('is_active')

        if is_active is None:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='is_active')
            raise ValidationError2(msg)

        return attrs


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = [
            'created_date',
            'id',
            'name',
            'name_uz',
            'name_ru',
            'short_name',
            'journal',
            'is_active',
        ]


class DocumentTypeForExternalUseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = [
            'id',
            'name',
            'short_name',
        ]

    def to_internal_value(self, data):
        return data.get('id')


class DocumentSubTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSubType
        fields = [
            'created_date',
            'id',
            'name',
            'short_name',
            'document_type',
        ]


class DocumentTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTitle
        fields = ['id', 'name', 'name_uz', 'name_ru', 'is_active']


class LanguageModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageModel
        fields = ['id', 'name', 'name_uz', 'name_ru', 'is_active']


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'code', 'name', 'alpha_2', 'alpha_3', 'status', 'currency_code']


class CountryCreateSerializer(CountrySerializer):
    class Meta(CountrySerializer.Meta):
        fields = CountrySerializer.Meta.fields

    def to_internal_value(self, data):
        return data.get('id')


class DistrictSerializer(serializers.ModelSerializer):
    region = SelectItemField(model='reference.Region', extra_field=['id', 'name', 'code'], required=True)

    class Meta:
        model = District
        fields = ['id', 'code', 'name', 'name_uz', 'name_ru', 'region', 'is_active']

    def validate(self, attrs):
        request = self.context.get('request')
        code = attrs.get('code')
        instance = self.instance

        if instance is not None:
            if instance.code == code:
                return attrs

        if District.objects.filter(code=code).exists():
            msg = get_response_message(request, 602)
            msg['message'] = msg['message'].format(object=f'Kod: {code}')
            raise ValidationError2(msg)

        return attrs


class RegionSerializer(serializers.ModelSerializer):
    country = SelectItemField(model='reference.Country', extra_field=['id', 'name', 'code'], required=False)

    class Meta:
        model = Region
        fields = ['id', 'code', 'name', 'name_uz', 'name_ru', 'is_active', 'country']

    def validate(self, attrs):
        request = self.context.get('request')
        code = attrs.get('code')
        instance = self.instance

        if instance is not None:
            if instance.code == code:
                return attrs

        # if Region.objects.filter(code=code).exists():
        #     msg = get_response_message(request, 602)
        #     msg['message'] = msg['message'].format(object=f'Kod: {code}')
        #     raise ValidationError2(msg)

        return attrs


class CityDistanceSerializer(serializers.ModelSerializer):
    from_city = SelectItemField(model='reference.Region', extra_field=['id', 'name'], required=False)
    to_city = SelectItemField(model='reference.Region', extra_field=['id', 'name'], required=False)
    distance = serializers.IntegerField(required=False)

    class Meta:
        model = CityDistance
        fields = ['id', 'from_city', 'to_city', 'distance']

    def validate(self, attrs):
        request = self.context.get('request')
        from_city = attrs.get('from_city')
        to_city = attrs.get('to_city')
        instance = self.instance

        if instance is not None:
            if instance.from_city == from_city and instance.to_city == to_city:
                return attrs

        if not from_city:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='from_city')
            raise ValidationError2(msg)

        if not to_city:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='to_city')
            raise ValidationError2(msg)

        if CityDistance.objects.filter(
                (Q(from_city=from_city) & Q(to_city=to_city)) | (Q(from_city=to_city) & Q(to_city=from_city))).exists():
            msg = get_response_message(request, 602)
            msg['message'] = msg['message'].format(object=f'{from_city} - {to_city}')
            raise ValidationError2(msg)

        return attrs


class DeliveryTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryType
        fields = ['id', 'name', 'name_uz', 'name_ru', 'is_active']


class PrioritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Priority
        fields = ['id', 'name', 'name_uz', 'name_ru', 'is_active']


class ExpenseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseType
        fields = ['id', 'name']


class AppVersionSerializer(serializers.ModelSerializer):
    file = SelectItemField(model='document.MobileApplication',
                           extra_field=['id', 'name', 'url'],
                           required=False)

    class Meta:
        model = AppVersion
        fields = ['id', 'type', 'version', 'min_version', 'url', 'file']


class AttendanceReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceReason
        fields = [
            'id',
            'code',
            'name',
            'name_uz',
            'name_ru',
            'description',
            'description_uz',
            'description_ru',
            'is_active',
        ]


class ExceptionEmployeeSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)

    class Meta:
        model = ExceptionEmployee
        fields = [
            'id',
            'user',
            'is_active',
            'valid_from',
            'valid_to',
            'activation_comment',
            'deactivation_comment',
        ]