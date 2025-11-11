from rest_framework import serializers

from apps.hr.models import PayrollPeriod, PayrollRow, PayrollCell
from utils.exception import ValidationError2, get_response_message
from utils.serializer import SelectItemField


class PayrollCellSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollCell
        fields = ("date", "code", "kind", "hours")


class PayrollRowSerializer(serializers.ModelSerializer):
    cells = PayrollCellSerializer(many=True, read_only=True)
    department = serializers.CharField(read_only=True, source='department.name')
    employee = serializers.CharField(read_only=True, source='employee.full_name')
    color = serializers.CharField(read_only=True, source='employee.color')

    class Meta:
        model = PayrollRow
        fields = ("id", "employee", "color", "department", "total_hours", "total_vacation",
                  "total_sick", "total_trip", "total_absent", "cells")


class PayrollPeriodListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = ("id", "name", "year", "month",
                  "mid_pay_date", "mid_locked", "final_pay_date",
                  "final_locked", "status", "note")

    def get_name(self, obj):
        if obj.type == 'department':
            return {
                "id": obj.department.id if obj.department else None,
                "name": obj.department.name if obj.department else "N/A",
                "type": "department"
            }
        elif obj.type == 'branch':
            return {
                "id": obj.company.id if obj.company else None,
                "name": obj.company.name if obj.company else "N/A",
                "type": "branch"
            }
        return None


class PayrollPeriodReadSerializer(serializers.ModelSerializer):
    rows = PayrollRowSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = ("id", "company", "year", "month",
                  "mid_pay_date", "mid_locked", "mid_approved_at",
                  "final_pay_date", "final_locked", "final_approved_at",
                  "status", "note", "rows")


class PayrollPeriodCreateSerializer(serializers.Serializer):
    date = serializers.DateField()


class PayrollApproveSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(),
                                help_text="List of approved PayrollPeriod IDs",
                                required=False, allow_null=True)
    approved = serializers.BooleanField(help_text="Approval status")
    note = serializers.CharField(required=False, allow_null=True)
    window = serializers.CharField(required=False, allow_null=True, help_text="Mid or Final Payment")

    def validate(self, attrs):
        request = self.context.get("request")
        ids = attrs.get("ids", None)
        window = attrs.get("window", None)

        if ids is None or len(ids) == 0:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='period IDs')
            raise ValidationError2(msg)

        if window not in ['mid', 'final']:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='window (mid or final)')
            raise ValidationError2(msg)

        return attrs
