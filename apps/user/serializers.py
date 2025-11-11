import datetime

from django.contrib.auth import authenticate
from django.db import models
from django.utils.crypto import get_random_string
from rest_framework import serializers

from apps.reference.models import EditableField
from apps.user.models import (
    AnnualSalary,
    MySalary,
    NotificationType,
    ProjectPermission,
    TopSigner,
    User,
    UserAssistant,
    UserEquipment,
    UserStatus,
    RoleModel,
    SignerModel,
    BirthdayReaction,
    MoodReaction,
    CustomAvatar,
    MySelectedContact,
    BirthdayComment,
    UserDevice, UserFavourite,
)
from apps.wchat.models import ChatMember
from base_model.serializers import ContentTypeMixin
from config.middlewares.current_user import get_current_user_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField
from utils.tools import get_or_none


class TreeSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = [
            'id',
            'user',
            'app_version',
            'device_type',
            'sim_id',
            'device_name',
            'product_name',
            'wifi_ip',
            'trip_verification',
        ]
        read_only_fields = ('user',)


class SendOTPPhoneSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20, required=False)
    otp_type = serializers.CharField(max_length=30, required=False)
    app_type = serializers.CharField(max_length=30, required=False, allow_null=True, allow_blank=True)
    app_signature = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)

    class Meta:
        fields = ['phone_number', 'otp_type', 'app_type', 'app_signature']

    def validate(self, attrs):
        request = self.context.get('request')
        phone_number = attrs.get('phone_number')
        if not phone_number:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='phone_number')
            raise ValidationError2(message)
        else:
            if not User.objects.filter(phone=phone_number).exists():
                message = get_response_message(request, 623)
                message['message'] = message['message'].format(object=phone_number)
                raise ValidationError2(message)
            else:
                user = User.objects.filter(phone=phone_number).first()
                if not user.is_user_active:
                    message = get_response_message(request, 702)
                    raise ValidationError2(message)
        return attrs


class VerifyOTPCodeSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20, required=False)
    otp_code = serializers.CharField(max_length=6, required=False)

    class Meta:
        fields = ['phone_number', 'otp_code']

    def validate(self, attrs):
        request = self.context.get('request')
        phone_number = attrs.get('phone_number')
        otp_code = attrs.get('otp_code')

        if not phone_number:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='phone_number')
            raise ValidationError2(message)
        else:
            if not User.objects.filter(phone=phone_number).exists():
                message = get_response_message(request, 623)
                message['message'] = message['message'].format(object=otp_code)
                raise ValidationError2(message)
            else:
                user = User.objects.filter(phone=phone_number).first()
                if not user.is_user_active:
                    message = get_response_message(request, 702)
                    raise ValidationError2(message)

        if not otp_code:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='otp_code')
            raise ValidationError2(message)

        return attrs


class LoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=100, required=True)
    password = serializers.CharField(max_length=68, write_only=True)
    tokens = serializers.SerializerMethodField(read_only=True)

    def get_tokens(self, obj):
        username = obj.get('username')
        tokens = User.objects.get(username=username).tokens
        return tokens

    class Meta:
        model = User
        fields = ('username', 'tokens', 'password')

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        request = self.context.get('request')
        user = authenticate(username=username, password=password)
        if not user:
            message = get_response_message(request, 701)
            raise ValidationError2(message)
        if not user.is_user_active:
            message = get_response_message(request, 702)
            raise ValidationError2(message)
        if not user.is_registered:
            message = get_response_message(request, 703)
            raise ValidationError2(message)

        return attrs


class LDAPLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100, required=True)
    password = serializers.CharField(max_length=100, required=True)


class EDSSignInSerializer(serializers.Serializer):
    pkcs7 = serializers.CharField(max_length=100000000000000, required=False)

    def validate(self, attrs):
        request = self.context.get('request')
        pkcs7 = attrs.get('pkcs7')
        if not pkcs7:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='pkcs7')
            raise ValidationError2(message)
        return attrs


class UserStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserStatus
        fields = ['id', 'name', 'code']


class UserSerializer(serializers.ModelSerializer):
    position = SelectItemField(model='company.Position', extra_field=['id', 'name', 'code'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    avatar = SelectItemField(model='document.File', extra_field=['id', 'name', 'url'], required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'father_name',
            'color',
            'position',
            'status',
            'top_level_department',
            'email',
            'avatar',
        ]

    def to_internal_value(self, data):
        return data.get('id')


class UserReferenceSerializer(serializers.ModelSerializer):
    position = SelectItemField(model='company.Position', extra_field=['id', 'name', 'code'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    avatar = SelectItemField(model='document.File', extra_field=['id', 'name', 'url'], required=False)
    private_chat_id = serializers.SerializerMethodField(read_only=True)
    is_selected = serializers.SerializerMethodField(read_only=True)
    favourite_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'cisco',
            'color',
            'email',
            'status',
            'position',
            'top_level_department',
            'department',
            'company',
            'avatar',
            'mobile_number',
            'room_number',
            'floor',
            'work_address',
            'phone_2',
            'private_chat_id',
            'is_selected',
            'favourite_id',
            'leave_end_date',
            'is_user_online',
        ]

    def get_private_chat_id(self, obj):
        user_id = get_current_user_id()
        qs = ChatMember.objects.select_related('chat').filter(created_by_id=user_id, user_id=obj.id)
        if qs.exists():
            return qs.first().chat.uid
        return None

    def get_is_selected(self, obj):
        user_id = get_current_user_id()
        qs = MySelectedContact.objects.filter(contact_id=user_id, user_id=obj.id)
        return qs.exists()

    def get_favourite_id(self, obj):
        user_id = get_current_user_id()
        qs = MySelectedContact.objects.filter(contact_id=user_id, user_id=obj.id).values_list("id", flat=True)
        return qs.first() if qs.exists() else None


class SetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    new_password = serializers.CharField(max_length=20)


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass


class ProjectPermissionSerializer(serializers.ModelSerializer):
    children = TreeSerializer(many=True, read_only=True)
    journal = SelectItemField(model='reference.Journal', extra_field=['id', 'name'], required=False)
    document_type = SelectItemField(model='reference.DocumentType', extra_field=['id', 'name'], required=False)
    document_sub_type = SelectItemField(model='reference.DocumentSubType', extra_field=['id', 'name'], required=False)

    class Meta:
        model = ProjectPermission
        fields = [
            'id',
            'name',
            'name_uz',
            'name_ru',
            'parent',
            'children',
            'url_path',
            'url_name',
            'method',
            'value',
            'content_type',
            'journal',
            'document_type',
            'document_sub_type',
            'all_visible'
        ]


class RoleModelSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(queryset=ProjectPermission.objects.all(),
                                                     many=True,
                                                     required=False)

    class Meta:
        model = RoleModel
        fields = ['id', 'name', 'is_active', 'permissions', 'created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        instance = self.instance
        is_active = attrs.get('is_active')
        name = attrs.get('name')

        if not name:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='name')
            raise ValidationError2(message)

        # Check if role has been set to user
        # If this role is set to user, it cannot be deactivated
        if is_active is False:
            user = User.objects.filter(roles__in=[instance.id])
            if user.exists():
                message = get_response_message(request, 637)
                message['message'] = message['message'].format(number=user.count())
                raise ValidationError2(message)

        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['permissions'] = ProjectPermissionSerializer(instance.permissions, many=True).data
        return data

    def create(self, validated_data):
        permissions = validated_data.pop('permissions', [])
        instance = RoleModel.objects.create(**validated_data)
        instance.permissions.set(permissions)
        return instance

    def update(self, instance, validated_data):
        permissions = validated_data.pop('permissions', [])
        instance = super().update(instance, validated_data)
        instance.permissions.set(permissions)
        return instance


class ProfileSerializer(serializers.ModelSerializer):
    # avatar = SelectItemField(model='document.File', extra_field=['id', 'name', 'url'], required=False)
    avatar = serializers.SerializerMethodField(read_only=True)
    department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    position = SelectItemField(model='company.Position', extra_field=['id', 'name', 'code'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name', 'region'], required=False)
    parent_dept_name = serializers.SerializerMethodField(read_only=True)
    roles = RoleModelSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'avatar',
            'begin_work_date',
            'birth_date',
            'cisco',
            'color',
            'company',
            'department',
            'email',
            'father_name',
            'first_name',
            'floor',
            'full_name',
            'id',
            'is_passcode_set',
            'is_superuser',
            'last_name',
            'parent_dept_name',
            'normalized_cisco',
            'phone',
            'phone_2',
            'position',
            'roles',
            'room_number',
            'show_birth_date',
            'show_mobile_number',
            'status',
            'table_number',
            'hik_person_code',
            'top_level_department',
            'unique_number',
            'username',
            'work_address',
        ]
        read_only_fields = ['id', 'first_name', 'last_name', 'full_name', 'is_superuser']

    def get_avatar(self, obj):
        return None

    def get_parent_dept_name(self, obj):
        if obj.department and obj.department.parent:
            return obj.department.parent.name
        return None

    def update(self, instance, validated_data):
        # Retrieve permissible fields dynamically from admin-defined settings or database
        permissible_fields = set(self.permissible_fields())

        update_data = {field: value for field, value in validated_data.items() if field in permissible_fields}

        for field, value in update_data.items():
            setattr(instance, field, value)

        instance.save()

        return instance

    def permissible_fields(self):
        """
        Fetch permissible fields from the database, admin settings, or configuration.
        For this example, we'll assume there's a model `EditableField` storing the field names.
        """

        # Query all permissible fields (stored in the database by admin)
        return EditableField.objects.values_list('field_name', flat=True)


class UserSearchSerializer(serializers.ModelSerializer):
    company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    position = SelectItemField(model='company.Position', extra_field=['id', 'name', 'code'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    avatar = SelectItemField(model='document.File', extra_field=['id', 'name', 'url'], required=False)
    private_chat_id = serializers.SerializerMethodField(read_only=True)
    is_selected = serializers.SerializerMethodField(read_only=True)
    favourite_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'birth_date',
            'full_name',
            'color',
            'cisco',
            'normalized_cisco',
            'department',
            'position',
            'first_name',
            'last_name',
            'father_name',
            'top_level_department',
            'company',
            'status',
            'email',
            'avatar',
            'mobile_number',
            'work_address',
            'room_number',
            'floor',
            'phone_2',
            'private_chat_id',
            'is_selected',
            'favourite_id',
            'leave_end_date',
            'is_user_online',
        ]

    def get_private_chat_id(self, obj):
        user_id = get_current_user_id()
        qs = ChatMember.objects.select_related('chat').filter(created_by_id=user_id, user_id=obj.id)
        if qs.exists():
            return qs.first().chat.uid
        return None

    def get_is_selected(self, obj):
        user_id = get_current_user_id()
        qs = MySelectedContact.objects.filter(contact_id=user_id, user_id=obj.id)
        return qs.exists()

    def get_favourite_id(self, obj):
        user_id = get_current_user_id()
        qs = MySelectedContact.objects.filter(contact_id=user_id, user_id=obj.id).values_list("id", flat=True)
        return qs.first() if qs.exists() else None


class UserListSerializer(ContentTypeMixin, serializers.ModelSerializer):
    company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    position = SelectItemField(model='company.Position', extra_field=['id', 'name', 'code'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    avatar = SelectItemField(model='document.File', extra_field=['id', 'name', 'url'], required=False)
    permissions = ProjectPermissionSerializer(many=True, read_only=True)
    is_favourite = serializers.SerializerMethodField()

    # roles = RoleModelSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'color',
            'company',
            'content_type',
            'department',
            'department_ids',
            'father_name',
            'first_name',
            'full_name',
            'id',
            'last_name',
            'position',
            'status',
            'top_level_department',
            'permissions',
            'roles',
            'hik_person_code',
            'normalized_cisco',
            'avatar',
            'is_favourite',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        # pinfl = attrs.get('pinfl')
        # phone = attrs.get('phone')
        username = attrs.get('username')
        instance = self.instance

        # If instance is present, it's an update operation
        # if instance:
        #     if instance.pinfl == pinfl and instance.phone == phone and instance.username == username:
        #         return attrs  # No changes in unique fields, skip further checks

        # Exclude the current instance when checking for duplicates (for updates)
        # if User.objects.exclude(id=instance.id if instance else None).filter(pinfl=pinfl).exists():
        #     msg = get_response_message(request, 602)
        #     msg['message'] = msg['message'].format(object=f'{pinfl} - PINFL')
        #     raise ValidationError2(msg)

        # if User.objects.exclude(id=instance.id if instance else None).filter(phone=phone).exists():
        #     msg = get_response_message(request, 602)
        #     msg['message'] = msg['message'].format(object=f'{phone} phone')
        #     raise ValidationError2(msg)

        # if User.objects.exclude(id=instance.id if instance else None).filter(username=phone).exists():
        #     msg = get_response_message(request, 602)
        #     msg['message'] = msg['message'].format(object=f'{username} username')
        #     raise ValidationError2(msg)

        return attrs

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # instance.department_ids = validated_data.get('department_ids', instance.department_ids)
        # instance.is_user_active = validated_data.get('is_user_active', instance.is_user_active)
        # instance.save()
        return instance

    def create(self, validated_data):
        phone = validated_data.get('phone')
        pinfl = validated_data.get('pinfl')

        if pinfl is None:
            pinfl = get_random_string(length=14, allowed_chars='0123456789')

        user = User.objects.create(**validated_data)
        user.username = phone
        user.pinfl = pinfl
        user.save()

        return user

    def get_is_favourite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return UserFavourite.objects.filter(user=request.user, favourite_user=obj).exists()

    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
    #     data['top_level_department'] = DepartmentSerializer(instance.top_level_department).data
    #     return data


class UserPersonalInformationSerializer(UserListSerializer):
    class Meta(UserListSerializer.Meta):
        model = User
        fields = UserListSerializer.Meta.fields + ['passport_seria',
                                                   'passport_number',
                                                   'passport_issue_date',
                                                   'passport_issued_by',
                                                   'passport_expiry_date',
                                                   ]


class UserAssistantSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    assistant = SelectItemField(model='user.User',
                                extra_field=['full_name', 'first_name', 'last_name',
                                             'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                             'top_level_department', 'department', 'company', 'email'],
                                required=False)

    class Meta:
        model = UserAssistant
        fields = ['id', 'user', 'assistant', 'is_active', 'created_date']
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context.get('request')
        user = attrs.get('user')
        assistant = attrs.get('assistant')

        if not user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=user.id)

        if not assistant:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='assistant')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=assistant.id)

        if UserAssistant.objects.filter(user_id=user.id, assistant_id=assistant.id).exists():
            message = get_response_message(request, 602)
            message['message'] = message['message'].format(object=f'{user.full_name} - {assistant.full_name}')
            raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        instance = UserAssistant.objects.create(**validated_data)
        if UserAssistant.objects.filter(user_id=instance.user_id).exclude(id=instance.id).exists():
            UserAssistant.objects.filter(user_id=instance.user_id).exclude(id=instance.id).update(is_active=False)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if UserAssistant.objects.filter(user_id=instance.user_id).exclude(id=instance.id).exists():
            UserAssistant.objects.filter(user_id=instance.user_id).exclude(id=instance.id).update(is_active=False)
        return instance


class TopSignerSerializer(serializers.ModelSerializer):
    from apps.reference.serializers import DocumentTypeForExternalUseSerializer

    doc_types = DocumentTypeForExternalUseSerializer(many=True, required=False)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    father_name = serializers.CharField(source='user.father_name', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    color = serializers.CharField(source='user.color', read_only=True)
    position = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField(read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)

    class Meta:
        model = TopSigner
        fields = [
            'color',
            'doc_types',
            'father_name',
            'first_name',
            'full_name',
            'id',
            'is_active',
            'last_name',
            'position',
            'status',
            'user',
            'user_id',
        ]

    def get_position(self, obj):
        return {
            'id': obj.user.position.id,
            'name': obj.user.position.name,
            'code': obj.user.position.code,
        }

    def get_status(self, obj):
        return {
            'id': obj.user.status.id,
            'name': obj.user.status.name,
            'code': obj.user.status.code,
        }

    def validate(self, attrs):
        request = self.context.get('request')
        user = attrs.get('user')
        doc_types = attrs.get('doc_types')

        if not user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=user.id)

        if not doc_types:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='doc_types')
            raise ValidationError2(message)

        if user and not user.assistants.exists():
            message = get_response_message(request, 619)
            message['message'] = message['message'].format(curator=user.full_name)
            raise ValidationError2(message)

        if request.method.lower() == 'post':
            if TopSigner.objects.filter(user_id=user.id).exists():
                message = get_response_message(request, 602)
                message['message'] = message['message'].format(object=user.full_name)
                raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        doc_types = validated_data.pop('doc_types')
        instance = TopSigner.objects.create(**validated_data)
        instance.doc_types.set(doc_types)
        return instance

    def update(self, instance, validated_data):
        doc_types = validated_data.pop('doc_types')
        instance = super().update(instance, validated_data)
        instance.doc_types.set(doc_types)
        return instance


class OrdinarySignerSerializer(serializers.ModelSerializer):
    from apps.reference.models import DocumentSubType

    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    doc_types = serializers.PrimaryKeyRelatedField(queryset=DocumentSubType.objects.all(), many=True, required=False)

    class Meta:
        model = SignerModel
        fields = ['id', 'user', 'doc_types', 'is_active']

    def validate(self, attrs):
        request = self.context.get('request')
        user = attrs.get('user')
        doc_types = attrs.get('doc_types')

        if not user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=user.id)

        if not doc_types:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='doc_types')
            raise ValidationError2(message)

        if request.method.lower() == 'post':
            if SignerModel.objects.filter(user_id=user.id).exists():
                message = get_response_message(request, 602)
                message['message'] = message['message'].format(object=user.full_name)
                raise ValidationError2(message)

        return attrs

    def to_representation(self, instance):
        from apps.reference.serializers import DocumentSubTypeSerializer
        data = super().to_representation(instance)
        data['doc_types'] = DocumentSubTypeSerializer(instance.doc_types, many=True).data
        return data

    def create(self, validated_data):
        doc_types = validated_data.pop('doc_types')
        instance = SignerModel.objects.create(**validated_data)
        instance.doc_types.set(doc_types)
        return instance

    def update(self, instance, validated_data):
        doc_types = validated_data.pop('doc_types')
        instance = super().update(instance, validated_data)
        instance.doc_types.set(doc_types)
        return instance


class UserSetPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'permissions']


class UserSetRoleSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(queryset=RoleModel.objects.all(),
                                               many=True,
                                               required=False)

    class Meta:
        model = User
        fields = ['id', 'roles']

    def validate(self, attrs):
        request = self.context.get('request')
        roles = attrs.get('roles')

        if not roles:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='roles')
            raise ValidationError2(message)
        else:
            for role in roles:
                get_or_none(RoleModel, request, id=role.id)

        return attrs


# class UserPermissionSerializer(serializers.ModelSerializer):
#     permission = SelectItemField(model='user.ProjectPermission', extra_field=['id', 'name'], required=False)
#
#     class Meta:
#         model = UserPermission
#         fields = ['id', 'user', 'permission', 'methods', 'is_active', 'created_date']
#
#     def validate(self, attrs):
#         permission = attrs.get('permission')
#         user = attrs.get('user')
#         request = self.context.get('request')
#
#         if not permission:
#             message = get_response_message(request, 600)
#             message['message'] = message['message'].format(type='permission')
#             raise ValidationError2(message)
#
#         if not user:
#             message = get_response_message(request, 600)
#             message['message'] = message['message'].format(type='user')
#             raise ValidationError2(message)
#
#         return attrs


class NotificationModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ['id', 'name', 'description', 'type']

    def validate(self, attrs):
        request = self.context.get('request')
        type = attrs.get('type')
        name = attrs.get('name')
        description = attrs.get('description')

        if not name:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='name')
            raise ValidationError2(message)

        if not description:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='description')
            raise ValidationError2(message)

        if not type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='type')
            raise ValidationError2(message)
        else:
            if type not in CONSTANTS.NOTIFICATION.TYPES.LIST:
                message = get_response_message(request, 606)
                message['message'] = message['message'].format(object=type)
                raise ValidationError2(message)

        return attrs


class NotificationTypeSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    notification = SelectItemField(model='user.NotificationModel',
                                   extra_field=['id', 'name', 'description', 'type'],
                                   required=False)

    class Meta:
        model = NotificationType
        fields = ['id', 'user', 'notification', 'is_mute', 'created_date']
        read_only_fields = ['id', 'created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        user = attrs.get('user')

        if not user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=user.id)

        return attrs


class NotificationTurnOnOrOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ['id', 'is_mute']
        read_only_fields = ['id']


class SetPasscodeSerializer(serializers.Serializer):
    """
    Serializer for set passcode.
    """
    passcode = serializers.CharField(required=True)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass


class MySalarySerializer(serializers.ModelSerializer):
    class Meta:
        model = MySalary
        fields = ['pay_name', 'summ', 'period', 'paid']


class AnnualSalarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnualSalary
        fields = ['month_value', 'monthly_salary']


class UserEquipmentSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False, )

    class Meta:
        model = UserEquipment
        fields = ['user', 'card_id', 'name', 'date_oper', 'inv_num', 'qr_text', 'responsible']


class BirthdayReactionSerializer(serializers.ModelSerializer):
    reaction_counts = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BirthdayReaction
        fields = ['birthday_user', 'reacted_by', 'reaction', 'created_date', 'reaction_counts']
        read_only_fields = ['reacted_by', 'created_date']

    def get_reaction_counts(self, obj):
        today = datetime.date.today()
        reactions = BirthdayReaction.objects.filter(birthday_user=obj.birthday_user,
                                                    created_date__date=today)
        counts = reactions.values('reaction').annotate(count=models.Count('reaction'))
        return counts

    def validate(self, attrs):
        request = self.context.get('request')
        birthday_user = attrs.get('birthday_user')
        reacted_by = request.user
        reaction = attrs.get('reaction')
        today = datetime.date.today()

        if birthday_user == reacted_by:
            message = get_response_message(request, 640)
            raise ValidationError2(message)

        if not birthday_user.birth_date or (birthday_user.birth_date.month != today.month or
                                            (birthday_user.birth_date.day != today.day)):
            message = get_response_message(request, 641)
            raise ValidationError2(message)

        if BirthdayReaction.objects.filter(birthday_user=birthday_user,
                                           reacted_by=reacted_by,
                                           reaction=reaction,
                                           created_date__date=today).exists():
            message = get_response_message(request, 642)
            raise ValidationError2(message)

        if not birthday_user:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='birthday_user')
            raise ValidationError2(message)
        else:
            get_or_none(User, request, id=birthday_user.id)

        if not reaction:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='reaction')
            raise ValidationError2(message)

        if reaction not in CONSTANTS.BIRTHDAY_REACTIONS.LIST:
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=reaction)
            raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        instance = BirthdayReaction.objects.create(**validated_data)
        instance.reacted_by = self.context.get('request').user
        instance.save()
        return instance


class BirthdayCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BirthdayComment
        fields = ['id', 'birthday_user', 'commented_by', 'comment', 'created_date']
        read_only_fields = ['id', 'commented_by', 'created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        birthday_user = attrs.get('birthday_user')
        comment = attrs.get('comment')
        commented_by = request.user
        today = datetime.date.today()

        if birthday_user == commented_by:
            message = get_response_message(request, 648)
            raise ValidationError2(message)

        if not birthday_user.birth_date or (
                birthday_user.birth_date.day != today.day and birthday_user.birth_date.month != today.month):
            message = get_response_message(request, 649)
            raise ValidationError2(message)

        if not comment:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='comment')
            raise ValidationError2(message)

        if len(comment) > 500:
            message = get_response_message(request, 650)
            message['message'] = message['message'].format(length='500')
            raise ValidationError2(message)

        if (BirthdayComment.objects.filter(birthday_user=birthday_user,
                                           commented_by=commented_by,
                                           created_date__date=today).exists() and
                request.method.lower() == 'post'):
            message = get_response_message(request, 642)
            raise ValidationError2(message)

        if request.method == 'POST':
            if BirthdayComment.objects.filter(
                    birthday_user=birthday_user,
                    commented_by=commented_by,
                    created_date__date=today
            ).exists():
                raise serializers.ValidationError("Siz ushbu foydalanuvchiga bugun allaqachon sharh yozgansiz!")

        return attrs

    def create(self, validated_data):
        instance = BirthdayComment.objects.create(**validated_data)
        instance.commented_by = self.context.get('request').user
        instance.save()
        return instance


class MoodReactionSerializer(serializers.ModelSerializer):
    reaction = serializers.CharField(required=False)

    class Meta:
        model = MoodReaction
        fields = ['id', 'user', 'reaction', 'created_date']
        read_only_fields = ['user', 'created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        reaction = attrs.get('reaction')
        today = datetime.date.today()

        if not reaction:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='reaction')
            raise ValidationError2(message)

        if reaction not in CONSTANTS.MOOD_REACTIONS.LIST:
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=reaction)
            raise ValidationError2(message)

        if MoodReaction.objects.filter(user=user, created_date__date=today).exists():
            message = get_response_message(request, 643)
            raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        instance = MoodReaction.objects.create(**validated_data)
        instance.user = self.context.get('request').user
        instance.save()
        return instance

    def update(self, instance, validated_data):
        birthday_user = instance.birthday_user
        reacted_by = self.context.get('request').user
        reaction = validated_data.get('reaction')
        today = datetime.date.today()

        query = BirthdayReaction.objects.filter(birthday_user=birthday_user,
                                                reacted_by=reacted_by,
                                                reaction=reaction,
                                                created_date__date=today)

        if query.exists():
            query.update(reaction=reaction)

        return instance


class CustomAvatarSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source='file.url', read_only=True)
    name = serializers.CharField(source='file.name', read_only=True)
    extension = serializers.CharField(source='file.extension', read_only=True)

    class Meta:
        model = CustomAvatar
        fields = ['id', 'url', 'name', 'extension', 'file', 'user', 'created_date']
        read_only_fields = ['created_date', 'user']

    def create(self, validated_data):
        file = validated_data.get('file')
        instance = CustomAvatar.objects.create(**validated_data)
        user = self.context.get('request').user
        # Set uploaded avatar as user's avatar
        user.avatar = file
        user.save()
        return instance


class MySelectedContactSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    is_user_online = serializers.BooleanField(source='user.is_user_online', read_only=True)
    private_chat_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MySelectedContact
        fields = ['id', 'user', 'is_user_online', 'private_chat_id', 'created_date']

    def get_private_chat_id(self, obj):
        qs = (ChatMember.objects.select_related('chat').
              filter(created_by_id=obj.contact_id, user_id=obj.user_id))
        if qs.exists():
            return qs.first().chat.uid
        return None

    def create(self, validated_data):
        instance = MySelectedContact.objects.create(**validated_data)
        instance.contact = self.context.get('request').user
        instance.save()
        return instance
