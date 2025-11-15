from rest_framework import serializers

from apps.company.models import Company, Position, Department
from apps.company.tasks import recalculate_sub_department_count
from apps.user.models import User
from utils.constant_ids import user_search_status_ids
from utils.constants import CONSTANTS
from utils.exception import ValidationError2, get_response_message
from utils.serializer import SelectItemField
from utils.tools import get_or_none


class SubDepartmentsTreeSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer_class = self.parent.parent.__class__
        serializer = serializer_class(value, context=self.context)
        return serializer.data


class CompanySerializer(serializers.ModelSerializer):
    region = SelectItemField(model='reference.Region', extra_field=['id', 'name', 'name_uz', 'name_ru'],
                             required=False)

    class Meta:
        model = Company
        fields = [
            'name',
            'name_ru',
            'name_uz',
            'code',
            'address',
            'address_ru',
            'address_uz',
            'phone',
            'condition',
            'id',
            'is_main',
            'region'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        code = attrs.get('code')
        instance = self.instance

        if instance is not None:
            if instance.code == code:
                return attrs

        if Company.objects.filter(code=code).exists():
            message = get_response_message(request, 602)
            message['message'] = message['message'].format(object=f'Kod: {code}')
            raise ValidationError2(message)

        return attrs


class MiniCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'name',
            'code',
            'id',
            'is_main',
        ]

    def to_internal_value(self, data):
        return data.get('id')


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = [
            'name',
            'name_uz',
            'name_ru',
            'code',
            'id',
            'is_active'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        name_uz = attrs.get('name_uz')
        name_ru = attrs.get('name_ru')
        code = attrs.get('code')
        instance = self.instance

        if name_uz is None:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='name_uz')
            raise ValidationError2(message)

        if name_ru is None:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='name_ru')
            raise ValidationError2(message)

        if code is None:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='code')
            raise ValidationError2(message)

        if instance is not None:
            if instance.code == code:
                return attrs

        if Position.objects.filter(code=code).exists():
            message = get_response_message(request, 602)
            message['message'] = message['message'].format(object=f'Kod: {code}')
            raise ValidationError2(message)

        return attrs


class DepartmentWithoutChildSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField(read_only=True)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name', 'code'], required=False)

    class Meta:
        model = Department
        fields = [
            'id',
            'name',
            'name_uz',
            'name_ru',
            'code',
            'company',
            'condition',
            'employee_count',
            'parent',
            'parent_code',
            'sub_department_count',
            'dep_index',
        ]

    def get_employee_count(self, obj):
        return obj.employees.count()


class DepartmentUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        request = self.context.get('request', None)
        user_id = attrs.get('user_id', None)
        user = get_or_none(User, request, id=user_id)

        if user.department_id is not None:
            msg = get_response_message(request, 622)
            msg['message'] = msg['message'].format(object=user.full_name)
            raise ValidationError2(msg)
        return attrs


class DepartmentSerializer(serializers.ModelSerializer):
    children = SubDepartmentsTreeSerializer(many=True, read_only=True)
    users = serializers.ListField(child=DepartmentUserSerializer(), write_only=True, required=False)
    employee_count = serializers.SerializerMethodField(read_only=True)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name', 'code'], required=False)

    class Meta:
        model = Department
        fields = [
            'id',
            'name',
            'name_ru',
            'name_uz',
            'code',
            'company',
            'condition',
            'employee_count',
            'parent',
            'parent_code',
            'sub_department_count',
            'users',
            'children',
            'hik_org_code',
            'dep_index',
        ]
        read_only_fields = [
            'sub_department_count',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        users = attrs.get('users', [])
        company = attrs.get('company')
        code = attrs.get('code')
        instance = self.instance

        if len(users) > 0:
            for obj in users:
                get_or_none(User, request, id=obj.get('user_id'))

        if company is None:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='filial')
            raise ValidationError2(message)

        if instance is not None:
            if instance.code == code:
                return attrs

        if Department.objects.filter(code=code).exists():
            msg = get_response_message(request, 602)
            msg['message'] = msg['message'].format(object=f'Kod: {code}')
            raise ValidationError2(msg)

        return attrs

    def create(self, validated_data):
        users = validated_data.pop('users', [])
        department = Department.objects.create(**validated_data)
        recalculate_sub_department_count(department.id)

        for obj in users:
            user = User.objects.get(id=obj.get('user_id'))
            user.department_id = department.id
            user.save()

        return department

    def update(self, instance, validated_data):
        users = validated_data.pop('users', [])
        instance = super(DepartmentSerializer, self).update(instance, validated_data)
        recalculate_sub_department_count(instance.id)

        for obj in users:
            user = User.objects.get(id=obj.get('user_id'))
            user.department_id = instance.id
            user.save()

        return instance

    def get_employee_count(self, obj):
        return obj.parent_department.count()


class SubDepartmentSerializer(serializers.ModelSerializer):
    has_child = serializers.SerializerMethodField(read_only=True)
    company = SelectItemField(model='company.Company', extra_field=['id', 'name', 'code'], required=False)

    class Meta:
        model = Department
        fields = [
            'name',
            'name_uz',
            'name_ru',
            'code',
            'condition',
            'company',
            'has_child',
            'id',
            'parent',
            'parent_code',
            'hik_org_code',
        ]

    def get_has_child(self, obj):
        return obj.children.exists()


class DepartmentActiveOrInactiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            'condition',
        ]


class DepartmentWithUserSerializer(serializers.ModelSerializer):
    children = SubDepartmentsTreeSerializer(many=True, read_only=True)
    users = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            'id',
            'name',
            'condition',
            'users',
            'children',
        ]

    def get_users(self, obj):
        from apps.user.serializers import UserReferenceSerializer
        status_ids = user_search_status_ids()
        users = obj.employees.filter(status_id__in=status_ids)
        return UserReferenceSerializer(users, many=True).data
