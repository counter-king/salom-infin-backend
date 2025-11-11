from django.db import transaction
from rest_framework import serializers

from apps.document.models import File
from apps.document.serializers import FileSerializer
from apps.hr.models import (
    DailySummary,
    WorkSchedule,
    EmployeeSchedule,
    HRBranchScope,
    HRDepartmentScope,
    AttendanceException,
    AttendanceExceptionApproval,
)
from apps.hr.tasks.payroll import create_attendance_exc_approval
from apps.user.models import User
from config.middlewares.current_user import get_current_user_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField, serialize_m2m


class AttendanceSerializer(serializers.ModelSerializer):
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'position', 'color', 'top_level_department',
                                        'table_number', 'company'],
                           read_only=True)
    user_status = SelectItemField(model="user.UserStatus",
                                  extra_field=['id', 'name', 'code', 'code_type'],
                                  required=False)
    violations = serializers.SerializerMethodField()

    class Meta:
        model = DailySummary
        fields = [
            'id',
            'user',
            'date',
            'first_check_in',
            'last_check_out',
            'worked_seconds',
            'late_minutes',
            'early_leave_minutes',
            'present',
            'absent',
            'person_code',
            'check_in_status',
            'check_out_status',
            'has_reason',
            'user_status',
            'violations',
        ]

    def _build_violation(self, summary, kind):
        # Use prefetched exceptions to avoid extra queries
        exc = None
        for e in getattr(summary, "prefetched_exceptions", []):
            if e.kind == kind:
                exc = e
                break
        return {
            "kind": kind,
            "has_appeal": exc is not None,
            "id": getattr(exc, "id", None),
            "status": getattr(exc, "status", None),
            "reason_id": getattr(getattr(exc, "reason", None), "id", None),
            "reason_name": getattr(getattr(exc, "reason", None), "name", None),
        }

    def get_violations(self, obj: DailySummary):
        out = []
        # late
        if obj.late_minutes > 0:
            out.append(self._build_violation(
                obj, "late"
            ))
        # early leave
        if obj.early_leave_minutes > 0:
            out.append(self._build_violation(
                obj, "early_leave"
            ))
        # absent
        if obj.absent:
            # You can pick plan_begin_time as "when" or leave null
            out.append(self._build_violation(
                obj, "absent"
            ))
        # missed check-in/out
        if obj.check_in_status == CONSTANTS.ATTENDANCE.CHECK_IN_STATUS.NOT_CHECKED:
            out.append(self._build_violation(obj, "missed_checkin"))
        if obj.check_out_status == CONSTANTS.ATTENDANCE.CHECK_IN_STATUS.NOT_CHECKED:
            out.append(self._build_violation(obj, "missed_checkout"))
        return out


class AttendanceHasReasonSerializer(serializers.ModelSerializer):
    has_reason = serializers.BooleanField(required=False)

    class Meta:
        model = DailySummary
        fields = ['id', 'has_reason']

    def validate(self, attrs):
        request = self.context.get('request')
        has_reason = attrs.get('has_reason')

        if has_reason is None:
            message = get_response_message(request, '600')
            message['message'] = message['message'].format(type='has_reason')

        return attrs


class WorkScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = [
            'id',
            'name',
            'name_uz',
            'name_ru',
            'start_time',
            'end_time',
            'lunch_start_time',
            'lunch_end_time',
            'is_default',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        lunch_start_time = attrs.get('lunch_start_time')
        lunch_end_time = attrs.get('lunch_end_time')

        if not start_time or not end_time:
            message = get_response_message(request, 895)
            raise ValidationError2(message)

        if start_time >= end_time:
            message = get_response_message(request, 894)
            raise ValidationError2(message)

            # ✅ 2. Validate lunch times if provided
        if lunch_start_time and lunch_end_time:
            # lunch start must be after work start
            if lunch_start_time <= start_time:
                message = get_response_message(request, 900)
                raise ValidationError2(message)

            # lunch end must be before work end
            if lunch_end_time >= end_time:
                message = get_response_message(request, 901)
                raise ValidationError2(message)

            # lunch end must be after lunch start
            if lunch_end_time <= lunch_start_time:
                message = get_response_message(request, 902)
                raise ValidationError2(message)

        elif lunch_start_time or lunch_end_time:
            # If only one of lunch times is given
            message = get_response_message(request, 903)
            raise ValidationError2(message)

        return attrs


class EmployeeScheduleSerializer(serializers.ModelSerializer):
    employee = SelectItemField(
        model="user.User",
        extra_field=['id', 'full_name', 'position', 'color', 'top_level_department',
                     'table_number', 'company'],
        required=False
    )
    schedule = SelectItemField(
        model="hr.WorkSchedule",
        extra_field=['id', 'name', 'start_time', 'end_time'],
        required=False
    )
    created_by = SelectItemField(
        model="user.User",
        extra_field=['full_name', 'position', 'color', 'top_level_department'],
        read_only=True
    )

    class Meta:
        model = EmployeeSchedule
        fields = [
            "id",
            "employee",
            "schedule",
            "notes",
            'is_default',
            "created_date",
            "created_by",
        ]


class BulkScheduleAssignSerializer(serializers.Serializer):
    schedule = serializers.IntegerField(min_value=1)
    employee_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class HRBranchScopeSerializer(serializers.ModelSerializer):
    branch = SelectItemField(
        model="company.Company",
        extra_field=['id', 'name', 'code', 'local_code'],
        required=False
    )
    hr_user = SelectItemField(
        model="user.User",
        extra_field=['id', 'full_name', 'position', 'color', 'company', 'status'],
        required=False
    )

    class Meta:
        model = HRBranchScope
        fields = [
            'id',
            'hr_user',
            'branch',
            'can_approve',
            'valid_from',
            'valid_until',
            'created_date',
        ]


class HRDepartmentScopeSerializer(serializers.ModelSerializer):
    department = SelectItemField(
        model="company.Department",
        extra_field=['id', 'name', 'code'],
        required=False
    )
    hr_user = SelectItemField(
        model="user.User",
        extra_field=['id', 'full_name', 'position', 'color', 'company', 'status'],
        required=False
    )

    class Meta:
        model = HRDepartmentScope
        fields = [
            'id',
            'hr_user',
            'department',
            'can_approve',
            'valid_from',
            'valid_until',
            'created_date',
        ]


class BulkBranchScopeAssignSerializer(serializers.Serializer):
    hr_user = serializers.IntegerField(min_value=1)
    branch_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    can_approve = serializers.BooleanField(required=False, default=False)
    valid_from = serializers.DateField(required=False, allow_null=True)
    valid_until = serializers.DateField(required=False, allow_null=True)


class BulkDepartmentScopeAssignSerializer(serializers.Serializer):
    hr_user = serializers.IntegerField(min_value=1)
    department_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    can_approve = serializers.BooleanField(required=False, default=False)
    valid_from = serializers.DateField(required=False, allow_null=True)
    valid_to = serializers.DateField(required=False, allow_null=True)


class ScopedUserSerializer(serializers.ModelSerializer):
    position = serializers.CharField(source="position.name", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "status", "color", "position"]

    def get_status(self, obj):
        return obj.status.dict() if hasattr(obj.status, "dict") else getattr(obj, "status", None)


class AttendanceExceptionApprovalSerializer(serializers.ModelSerializer):
    user = SelectItemField(
        model="user.User",
        extra_field=['id', 'full_name', 'position', 'color'],
        required=False, read_only=True
    )

    class Meta:
        model = AttendanceExceptionApproval
        fields = ['id', 'user', 'type', 'is_approved', 'action_time', 'decision_note']


class AttendanceExceptionSerializer(serializers.ModelSerializer):
    employee = SelectItemField(
        model="user.User",
        extra_field=['id', 'full_name', 'position', 'color'],
        required=False, read_only=True
    )
    attendance = SelectItemField(
        model="hr.DailySummary",
        extra_field=['id', 'date', 'first_check_in', 'last_check_out', 'worked_seconds',
                     'late_minutes', 'early_leave_minutes', 'present', 'absent'],
        required=False
    )
    reason = SelectItemField(
        model="reference.AttendanceReason",
        extra_field=['id', 'name', 'code'],
        required=False
    )
    attachments = FileSerializer(many=True, required=False)
    approvals = AttendanceExceptionApprovalSerializer(many=True, required=False, read_only=True)

    class Meta:
        model = AttendanceException
        fields = [
            "attachments",
            "attendance",
            "created_date",
            "id",
            "kind",
            "modified_date",
            "note",
            "reason",
            "status",
            "employee",
            "worked_time",
            'approvals',
        ]
        read_only_fields = [
            "created_date",
            "decision_note",
            "modified_date",
            "status",
            "worked_time",
        ]

    def create(self, validated_data):
        attachments = validated_data.pop("attachments", [])
        approvals = validated_data.pop("approvals", [])
        current_user_id = get_current_user_id()
        request = self.context.get("request")

        with transaction.atomic():
            # set employee at creation (1 save)
            instance = AttendanceException.objects.create(
                employee_id=current_user_id,
                **validated_data
            )

            # Save attachments (assuming serialize_m2m handles ids/dicts)
            serialize_m2m('create', File, 'attachments', attachments, instance)

            # Manager routing info
            employee = instance.employee  # related object
            company = getattr(employee, "company", None)
            is_main = getattr(company, "is_main", None)
            top_dept_id = getattr(employee, "top_level_department_id", None)

            if is_main is None or top_dept_id is None:
                # Avoid scheduling a broken task; adjust message/log as needed
                # Raise ValidationError to roll back entirely
                message = get_response_message(request, 896)
                raise ValidationError2(message)
            else:
                org_type = 'department' if is_main else 'branch'

                # schedule AFTER COMMIT to avoid race with readers/tasks
                def _enqueue():
                    # create_attendance_exc_approval(instance.id, top_dept_id, org_type)
                    create_attendance_exc_approval.delay(instance.id, top_dept_id, org_type)

                transaction.on_commit(_enqueue)

        return instance

    def update(self, instance, validated_data):
        attachments = validated_data.pop("attachments", [])
        approvals = validated_data.pop("approvals", [])
        instance = super().update(instance, validated_data)
        serialize_m2m('update', File, 'attachments', attachments, instance)
        return instance


class ApproveOrRejectExceptionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
