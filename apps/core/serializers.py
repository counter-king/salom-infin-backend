from django.db.models import Max
from rest_framework import serializers

from apps.company.models import Department
from apps.core.models import (
    PageRanking,
    BranchManager,
    DepartmentManager,
)
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField


class PageRankingSerializer(serializers.ModelSerializer):
    rank = serializers.IntegerField(required=False)
    comment = serializers.CharField(required=False, max_length=255)

    class Meta:
        model = PageRanking
        fields = ['id', 'page_url', 'rank', 'comment', 'created_date', 'created_by']
        read_only_fields = ['created_date', 'created_by']

    def validate(self, attrs):
        request = self.context.get('request')
        rank = attrs.get('rank')
        comment = attrs.get('comment')

        if not rank:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='rank')
            raise ValidationError2(message)

        if rank and (rank < 0 or rank > 5):
            message = get_response_message(request, 644)
            raise ValidationError2(message)

        if rank <= 3 and not comment:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='comment')
            raise ValidationError2(message)

        return attrs


class VerifyDGSISerializer(serializers.Serializer):
    document_id = serializers.CharField(max_length=255)
    document = serializers.CharField(max_length=100000000000000)


class DepartmentManagerSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['id', 'full_name', 'first_name', 'last_name',
                                        'father_name', 'position', 'status'],
                           required=False)

    department = SelectItemField(model='company.Department', extra_field=['id', 'name', ], required=False)

    class Meta:
        model = DepartmentManager
        fields = ['id', 'department', 'user', 'is_primary', 'is_active', 'sort_order', 'valid_from', 'valid_until']

    def create(self, validated_data):
        # Append to bottom if sort_order is missing
        if 'sort_order' not in validated_data or validated_data.get('sort_order') is None:
            max_so = (
                         DepartmentManager.objects
                         .filter(department=validated_data['department'])
                         .aggregate(m=Max('sort_order'))['m']) or -1
            validated_data['sort_order'] = max_so + 1

        obj = super().create(validated_data)

        # If primary, unset others atomically (DB also guarded by partial unique if you added it)
        if obj.is_primary:
            (DepartmentManager.objects
             .filter(department=obj.department)
             .exclude(pk=obj.pk)
             .update(is_primary=False))

        return obj


class BranchManagerSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['id', 'full_name', 'first_name', 'last_name',
                                        'father_name', 'position', 'status'],
                           required=False)

    # branch = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = BranchManager
        fields = ['id', 'branch', 'user', 'is_primary', 'is_active', 'sort_order', 'valid_from', 'valid_until']

    def create(self, validated_data):
        # Append to bottom if sort_order is missing
        if 'sort_order' not in validated_data or validated_data.get('sort_order') is None:
            max_so = BranchManager.objects.filter(branch=validated_data['branch']).aggregate(m=Max('sort_order'))[
                         'm'] or -1
            validated_data['sort_order'] = max_so + 1

        obj = super().create(validated_data)

        # If primary, unset others atomically (DB also guarded by partial unique if you added it)
        if obj.is_primary:
            (BranchManager.objects
             .filter(branch=obj.branch)
             .exclude(pk=obj.pk)
             .update(is_primary=False))

        return obj


class ManagersReorderSerializer(serializers.Serializer):
    object_id = serializers.IntegerField(required=False, allow_null=True)
    ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_null=True)


class MoveToSerializer(serializers.Serializer):
    position = serializers.IntegerField(allow_null=True)


class ManagersSyncSerializer(serializers.Serializer):
    object_id = serializers.IntegerField()  # branch_id or department_id
    managers_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )

    def validate_managers_ids(self, value):
        # ensure unique order (no dupes)
        if len(value) != len(set(value)):
            raise ValidationError2({"message": "managers_ids must be unique."})
        return value
