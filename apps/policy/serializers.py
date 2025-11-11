from __future__ import annotations

from django.db import IntegrityError
from rest_framework import serializers

from apps.policy.logic import compile_condition_json
from apps.policy.models import Resource, Action, Role, Policy, RoleAssignment
from apps.reference.serializers import RecursiveSerializer
from utils.exception import ValidationError2
from utils.serializer import SelectItemField


class ResourceSerializer(serializers.ModelSerializer):
    children = RecursiveSerializer(many=True, read_only=True)

    class Meta:
        model = Resource
        fields = ("id", "key", "display_name", "description", "children", "created_date", "modified_date")
        read_only_fields = fields


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ("id", "key", "description", "created_date", "modified_date")
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "description", "is_active", "is_system", "created_date", "modified_date")
        read_only_fields = ("id", "created_at", "updated_at", "is_system")


class PolicySerializer(serializers.ModelSerializer):
    # Show enum choices to the client
    condition_kind = serializers.ChoiceField(choices=Policy.ConditionKind.choices)
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
    resource = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.all(), required=False)
    action = serializers.PrimaryKeyRelatedField(queryset=Action.objects.all(), required=False)

    class Meta:
        model = Policy
        fields = (
            "id",
            "role", "resource", "action",
            "effect",
            "condition_kind",
            # parameters (all optional, used depending on kind)
            "param_departments", "param_owner_field",
            "param_time_start_hhmm", "param_time_end_hhmm",
            "param_journal_ids", "param_doc_type_ids", "param_doc_sub_type_ids",
            "param_advanced_ast", "valid_from", "valid_until",
            # compiled + scope + misc
            "condition", "org_key", "priority", "enabled",
            "created_date", "modified_date",
        )
        read_only_fields = ("id", "condition", "created_date", "modified_date")

    def validate(self, attrs):
        kind = attrs.get("condition_kind", self.instance.condition_kind if self.instance else "none")
        # light validation (mirrors Admin form)
        if kind == Policy.ConditionKind.SPECIFIC_DEPTS and not attrs.get("param_departments"):
            raise serializers.ValidationError({"param_departments": "Provide at least one department id."})
        if kind == Policy.ConditionKind.TIME_WINDOW:
            if not attrs.get("param_time_start_hhmm") or not attrs.get("param_time_end_hhmm"):
                raise serializers.ValidationError({"param_time_start_hhmm": "Start/End time required (HH:MM)."})
        if kind == Policy.ConditionKind.SPECIFIC_JOURNALS and not attrs.get("param_journal_ids"):
            raise serializers.ValidationError({"param_journal_ids": "Provide journal ids."})
        if kind == Policy.ConditionKind.SPECIFIC_DOC_TYPES and not attrs.get("param_doc_type_ids"):
            raise serializers.ValidationError({"param_doc_type_ids": "Provide document type ids."})
        if kind == Policy.ConditionKind.SPECIFIC_DOC_SUBTYPES and not attrs.get("param_doc_sub_type_ids"):
            raise serializers.ValidationError({"param_doc_sub_type_ids": "Provide document sub type ids."})
        return attrs

    def to_representation(self, instance):
        policy = super(PolicySerializer, self).to_representation(instance)
        policy['role'] = RoleSerializer(instance.role).data
        policy['action'] = ActionSerializer(instance.action).data
        policy['resource'] = ResourceSerializer(instance.resource).data
        return policy

    def create(self, validated):
        obj = Policy(**validated)
        obj.condition_json = compile_condition_json(obj)
        try:
            obj.save()
        except IntegrityError as e:
            raise ValidationError2({"message": [str(e)]})
        return obj

    def update(self, instance, validated):
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.condition_json = compile_condition_json(instance)
        try:
            instance.save()
        except IntegrityError as e:
            raise ValidationError2({"message": [str(e)]})
        return instance


class RoleAssignmentSerializer(serializers.ModelSerializer):
    user = SelectItemField(model="user.User",
                           extra_field=["id", "first_name", "last_name", "top_level_department", "color"],
                           required=False)
    role = SelectItemField(model="policy.Role",
                           extra_field=["id", "name", "description"],
                           required=False)

    class Meta:
        model = RoleAssignment
        fields = (
            "id",
            "role", "user",
            "group", "org_key",
            "valid_from", "valid_until",
            "enabled", "created_date", "modified_date")
        read_only_fields = ("id", "created_date", "modified_date")

    def validate(self, attrs):
        user = attrs.get("user")
        group = attrs.get("group")
        if not user and not group:
            raise ValidationError2({"message": "Provide user or group"})
        return attrs
