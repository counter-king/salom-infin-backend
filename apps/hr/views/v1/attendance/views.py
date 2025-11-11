from typing import Dict, Any

from django.db import transaction
from django.db.models import Count, Q, OuterRef, Exists, Sum, Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views, viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hr.filters import DailySummaryFilter, EmployeeScheduleFilter, AttendanceExceptionFilter
from apps.hr.models import DailySummary, IABSCalendar
from apps.hr.models.attendance import (
    WorkSchedule,
    EmployeeSchedule,
    HRBranchScope,
    HRDepartmentScope,
    AttendanceException,
)
from apps.hr.serializers.v1.attendance import (
    AttendanceSerializer,
    AttendanceHasReasonSerializer,
    WorkScheduleSerializer,
    EmployeeScheduleSerializer,
    BulkScheduleAssignSerializer,
    HRBranchScopeSerializer,
    BulkBranchScopeAssignSerializer,
    HRDepartmentScopeSerializer,
    BulkDepartmentScopeAssignSerializer,
    ScopedUserSerializer,
    AttendanceExceptionSerializer, ApproveOrRejectExceptionSerializer,
)
from apps.hr.services.scheduling import bulk_assign_default_schedule
from apps.policy.permissions import HasDynamicPermission
from apps.policy.scopes.attendance_exceptions import AttendanceExceptionListScope
from apps.policy.scopes.registry import get_strategy
from apps.user.models import User
from utils.constant_ids import user_search_status_ids
from utils.constants import CONSTANTS
from utils.exception import ValidationError2, get_response_message


class AttendanceSummaryTotals(views.APIView):
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING)
    company = openapi.Parameter(
        'company', openapi.IN_QUERY,
        description="Company ID",
        type=openapi.TYPE_INTEGER)

    @swagger_auto_schema(manual_parameters=[start_date, end_date, company], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        company = request.GET.get('company')

        if not start_date or not end_date:
            return Response({"message": "start_date and end_date are required"}, status=400)

        company_id = int(company) if company else None
        data = self.summarize_month_totals(start_date, end_date, company_id)
        return Response(data)

    def summarize_month_totals(self, start_date: str, end_date: str, company_id: int | None):
        # Base queryset with required filters
        query = DailySummary.objects.filter(date__gte=start_date, date__lte=end_date)

        # Apply company filter only if provided
        if company_id:
            query = query.filter(user__company_id=company_id)

        totals = query.aggregate(
            on_time=Count("id", filter=Q(present=True, late_minutes=0)),
            lateness=Count("id", filter=Q(late_minutes__gt=0)),
            early_leaves=Count("id", filter=Q(early_leave_minutes__gt=0)),
            absent=Count("id", filter=Q(absent=True))
        )

        status_ids = user_search_status_ids()
        user_query = User.objects.filter(status_id__in=status_ids)
        if company_id:
            user_query = user_query.filter(company_id=company_id)

        totals['not_registered_on_faceid'] = user_query.filter(hik_person_code__isnull=True).count()

        return [totals]


class AttendanceViewSet(viewsets.GenericViewSet,
                        mixins.ListModelMixin,
                        mixins.RetrieveModelMixin):
    # queryset = DailySummary.objects.all()
    serializer_class = AttendanceSerializer
    search_fields = ['user__first_name', 'user__last_name']
    ordering = ['-date']
    filterset_class = DailySummaryFilter

    def get_queryset(self):
        qs = (
            DailySummary.objects
            .select_related("user", "user__company", "user__top_level_department")
            .prefetch_related(
                Prefetch(
                    "exceptions",
                    queryset=AttendanceException.objects.select_related("reason"),
                    to_attr="prefetched_exceptions",
                )
            )
        )

        if self.request.GET.get("status") == "not_registered_on_faceid":
            return qs.none()

        return qs

    def list(self, request, *args, **kwargs):
        # Special branch: users not registered on faceid (no DailySummary rows)
        if request.query_params.get("status") == "not_registered_on_faceid":
            status_ids = user_search_status_ids()
            company_id = request.query_params.get("company_id")

            user_qs = User.objects.filter(
                status_id__in=status_ids,
                hik_person_code__isnull=True,
            ).select_related("company", "top_level_department")

            if company_id:
                user_qs = user_qs.filter(company_id=company_id)

            # Build UNSAVED DailySummary instances so ModelSerializer works unchanged
            synthetic_rows = []
            for u in user_qs:
                synthetic_rows.append(DailySummary(
                    # id will be None (not saved) – serializer will output null
                    user=u,
                    date=None,
                    first_check_in=None,
                    last_check_out=None,
                    worked_seconds=0,
                    late_minutes=0,
                    early_leave_minutes=0,
                    present=False,
                    absent=False,
                    person_code=None
                ))

            page = self.paginate_queryset(synthetic_rows)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(synthetic_rows, many=True)
            return Response(serializer.data)

        # Default behavior (list actual DailySummary rows)
        return super().list(request, *args, **kwargs)


class MyAttendanceViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin):
    serializer_class = AttendanceSerializer
    search_fields = ['user__first_name', 'user__last_name']
    ordering = ['-date']
    filterset_class = DailySummaryFilter
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY, description="YYYY-MM-DD", type=openapi.TYPE_STRING)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY, description="YYYY-MM-DD", type=openapi.TYPE_STRING)

    def get_queryset(self):
        user = self.request.user
        qs = (
            DailySummary.objects
            .filter(user=user)
            .select_related("user", "user__company", "user__top_level_department")
            .prefetch_related(
                Prefetch(
                    "exceptions",
                    queryset=AttendanceException.objects.select_related("reason"),
                    to_attr="prefetched_exceptions",
                )
            )
        )
        return qs

    def get_serializer_class(self):
        if self.action == 'has-reason':
            return AttendanceHasReasonSerializer
        return super().get_serializer_class()

    @action(detail=True,
            methods=['patch'],
            url_path='has-reason',
            url_name='has-reason',
            serializer_class=AttendanceHasReasonSerializer)
    def has_reason(self, request, pk=None, *args, **kwargs):
        """
        Marks whether the attendance exception for this day has a valid reason.
        """
        instance = self.get_queryset().get(pk=pk)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    @action(detail=False, methods=['get'], url_path='summary', url_name='summary')
    def summary(self, request, *args, **kwargs):
        """
        Get attendance summary totals for the current user over a date range.
        This data can be used only on the user's own profile.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if not start_date or not end_date:
            return Response({"message": "start_date and end_date are required"}, status=400)

        user = request.user
        data = self.summarize_totals(user, start_date, end_date)
        return Response(data)

    def summarize_totals(self, user: User, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Calculates totals between start_date and end_date (inclusive).

        - Counts working/off days from IABSCalendar
        - Sums worked seconds for 'present' days (optionally you can drop late filter)
        - Counts absent days and converts to hours (8h/day)
        - Lists holidays (name, name_ru) in range
        """

        cal_qs = IABSCalendar.objects.filter(date__range=(start_date, end_date))

        cal_agg = cal_qs.aggregate(
            working_days=Count("id", filter=Q(work_day=1)),
            off_working_days=Count("id", filter=Q(work_day=0)),
        )

        # NOTE: distinct() on values(...) requires Postgres for multi-column distinct.
        holidays = list(
            cal_qs.filter(is_holiday=True)
            .order_by("date")
            .values("date", "holiday_name", "holiday_name_ru")
            .distinct()
        )

        ds_qs = DailySummary.objects.filter(user=user, date__range=(start_date, end_date))

        ds_agg = ds_qs.aggregate(
            worked_seconds=Coalesce(Sum("worked_seconds", filter=Q(present=True)), 0),
            absent_days=Coalesce(Count("id", filter=Q(absent=True)), 0),
        )

        working_hours = int(cal_agg['working_days']) * 8
        worked_hours = int(ds_agg["worked_seconds"]) // 3600
        absent_hours = int(ds_agg["absent_days"]) * 8

        return {
            "working_days": cal_agg["working_days"],
            "off_working_days": cal_agg["off_working_days"],
            "holidays": [{"name": h["holiday_name"], "name_ru": h["holiday_name_ru"], "date": h["date"]} for h in
                         holidays],
            "working_hours": working_hours,  # total hours need to work for given period
            "worked_hours": worked_hours,  # total worked hours for given period
            "absent_hours": absent_hours,
            "absent_days": int(ds_agg["absent_days"]),
        }


class WorkScheduleViewSet(viewsets.ModelViewSet):
    queryset = WorkSchedule.objects.all()  # ordering handled by model Meta
    serializer_class = WorkScheduleSerializer
    search_fields = ['name']

    def perform_destroy(self, instance):
        # Delete and then ensure there's still a default
        super().perform_destroy(instance)
        WorkSchedule.objects.ensure_some_default()

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """
        Explicit endpoint: POST /workschedules/{id}/set_default/
        """
        WorkSchedule.objects.set_default(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeScheduleViewSet(viewsets.ModelViewSet):
    queryset = EmployeeSchedule.objects.select_related("employee", "schedule")
    serializer_class = EmployeeScheduleSerializer
    filterset_class = EmployeeScheduleFilter
    search_fields = ["employee__first_name", "employee__last_name", "employee__table_number", "schedule__name"]

    def perform_create(self, serializer):
        obj = serializer.save()
        if obj.is_default:
            # THIS is where your set_default must be used
            EmployeeSchedule.objects.set_default(
                employee_id=obj.employee_id,
                schedule_id=obj.schedule_id,
                notes=obj.notes or "",
            )

    def perform_update(self, serializer):
        obj = serializer.save()
        if obj.is_default:
            EmployeeSchedule.objects.set_default(
                employee_id=obj.employee_id,
                schedule_id=obj.schedule_id,
                notes=obj.notes or "",
            )

    @action(detail=False,
            methods=['post'],
            url_path='bulk-assign',
            serializer_class=BulkScheduleAssignSerializer)
    def bulk_assign(self, request):
        """
        POST /employee-schedules/bulk-assign/
        {
          "schedule": 5,
          "employee_ids": [10, 11, 12],
          "notes": "Night shift",
        }
        """
        ser = BulkScheduleAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user_id = request.user.id

        try:
            result = bulk_assign_default_schedule(
                schedule_id=data["schedule"],
                employee_ids=data["employee_ids"],
                assigned_by_id=user_id,
                notes=data.get("notes", "")
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "schedule_id": result.schedule_id,
                "updated_default_count": result.updated_default_count,
                "created_rows": result.created_rows,
                "switched_from_other": result.switched_from_other,
                "skipped_missing_employees": result.skipped_missing_employees,
            },
            status=status.HTTP_200_OK,
        )


class HRBranchScopeViewSet(viewsets.ModelViewSet):
    queryset = HRBranchScope.objects.select_related("hr_user", "branch")
    serializer_class = HRBranchScopeSerializer
    filterset_fields = ["hr_user", "branch"]
    search_fields = ["hr_user__first_name", "hr_user__last_name", "branch__name"]

    @action(detail=False,
            methods=['post'],
            url_path='bulk-assign',
            serializer_class=BulkBranchScopeAssignSerializer)
    def bulk_assign(self, request):
        """
        POST /hr/branch-scopes/bulk-assign/
        {
          "hr_user": 7,
          "branch_ids": [1,2,3],
          "can_approve": true,
          "valid_from": "2025-10-01",
          "valid_to": null
        }
        Creates missing (hr_user, branch) rows; updates existing only if values differ.
        """
        serializer = BulkBranchScopeAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        hr_user_id = v["hr_user"]
        # dedupe while preserving order
        branch_ids = list(dict.fromkeys(v["branch_ids"]))
        can_approve = v.get("can_approve", False)
        valid_from = v.get("valid_from")
        valid_to = v.get("valid_to")

        if not branch_ids:
            return Response({"created": 0, "updated": 0}, status=status.HTTP_200_OK)

        with transaction.atomic():
            # 1) Load existing scopes for this user & these branches
            existing_qs = (HRBranchScope.objects
                           .select_for_update()
                           .filter(hr_user_id=hr_user_id, branch_id__in=branch_ids)
                           .only("id", "branch_id", "can_approve", "valid_from", "valid_to"))

            existing_by_branch = {obj.branch_id: obj for obj in existing_qs}

            # 2) Split to create vs maybe-update
            to_create_ids = [bid for bid in branch_ids if bid not in existing_by_branch]
            to_update_objs = []
            for bid, obj in existing_by_branch.items():
                if (obj.can_approve != can_approve or
                        obj.valid_from != valid_from or
                        obj.valid_to != valid_to):
                    obj.can_approve = can_approve
                    obj.valid_from = valid_from
                    obj.valid_to = valid_to

                    to_update_objs.append(obj)

            # 3) bulk create
            new_objs = [
                HRBranchScope(
                    hr_user_id=hr_user_id,
                    branch_id=bid,
                    can_approve=can_approve,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
                for bid in to_create_ids
            ]
            if new_objs:
                HRBranchScope.objects.bulk_create(new_objs, ignore_conflicts=False)

            # 4) bulk update (or a single UPDATE if all rows get same values)
            updated = 0
            if to_update_objs:
                fields = ["can_approve", "valid_from", "valid_to"]
                updated = HRBranchScope.objects.bulk_update(to_update_objs, fields)

        return Response({"created": len(new_objs), "updated": updated}, status=status.HTTP_200_OK)


class HRDepartmentScopeViewSet(viewsets.ModelViewSet):
    queryset = HRDepartmentScope.objects.select_related("hr_user", "department")
    serializer_class = HRDepartmentScopeSerializer
    filterset_fields = ["hr_user", "department"]
    search_fields = ["hr_user__first_name", "hr_user__last_name", "department__name"]

    @action(detail=False,
            methods=['post'],
            url_path='bulk-assign',
            serializer_class=BulkDepartmentScopeAssignSerializer)
    def bulk_assign(self, request):
        """
        POST /hr/department-scopes/bulk-assign/
        {
          "hr_user": 7,
          "department_ids": [1,2,3],
          "can_approve": true,
          "valid_from": "2025-10-01",
          "valid_to": null
        }
        Creates missing (hr_user, department) rows; updates existing only if values differ.
        """
        serializer = BulkDepartmentScopeAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        hr_user_id = v["hr_user"]
        # dedupe while preserving order
        department_ids = list(dict.fromkeys(v["department_ids"]))
        can_approve = v.get("can_approve", False)
        valid_from = v.get("valid_from")
        valid_to = v.get("valid_until")

        if not department_ids:
            return Response({"created": 0, "updated": 0}, status=status.HTTP_200_OK)

        with transaction.atomic():
            # 1) Load existing scopes for this user & these departments
            existing_qs = (HRDepartmentScope.objects
                           .select_for_update()
                           .filter(hr_user_id=hr_user_id, department_id__in=department_ids)
                           .only("id", "department_id", "can_approve", "valid_from", "valid_until"))

            existing_by_department = {obj.department_id: obj for obj in existing_qs}

            # 2) Split to create vs maybe-update
            to_create_ids = [did for did in department_ids if did not in existing_by_department]
            to_update_objs = []
            for did, obj in existing_by_department.items():
                if (obj.can_approve != can_approve or
                        obj.valid_from != valid_from or
                        obj.valid_to != valid_to):
                    obj.can_approve = can_approve
                    obj.valid_from = valid_from
                    obj.valid_to = valid_to
                    to_update_objs.append(obj)

            # 3) bulk create
            new_objs = [
                HRDepartmentScope(
                    hr_user_id=hr_user_id,
                    department_id=did,
                    can_approve=can_approve,
                    valid_from=valid_from,
                    valid_until=valid_to,
                )
                for did in to_create_ids
            ]
            if new_objs:
                HRDepartmentScope.objects.bulk_create(new_objs, ignore_conflicts=False)
            # 4) bulk update (or a single UPDATE if all rows get same values)
            updated = 0
            if to_update_objs:
                fields = ["can_approve", "valid_from", "valid_until"]
                updated = HRDepartmentScope.objects.bulk_update(to_update_objs, fields)
        return Response({"created": len(new_objs), "updated": updated}, status=status.HTTP_200_OK)


class AssignedHrUsersView(viewsets.GenericViewSet,
                          mixins.ListModelMixin):
    """
    List of users who have at least one HR scope
    (branch or department). You can also filter users who have only branch,
    only department, or both via ?scope_type=branch|department|both.
    """
    serializer_class = ScopedUserSerializer
    search_fields = ["first_name", "last_name", "father_name", "position__name"]

    def get_queryset(self):
        status_ids = user_search_status_ids()

        # Subqueries: does this user have any branch/department scope?
        branch_exists = HRBranchScope.objects.filter(hr_user_id=OuterRef("pk"))
        dept_exists = HRDepartmentScope.objects.filter(hr_user_id=OuterRef("pk"))

        qs = (
            User.objects
            .filter(status_id__in=status_ids)
            .annotate(
                has_branch_scope=Exists(branch_exists),
                has_department_scope=Exists(dept_exists),
            )
            .filter(Q(has_branch_scope=True) | Q(has_department_scope=True))
            .select_related("position", "status")
            .distinct()
        )

        # Optional filter by scope_type
        scope_type = self.request.GET.get("scope_type")
        if scope_type == "branch":
            qs = qs.filter(has_branch_scope=True, has_department_scope=False)
        elif scope_type == "department":
            qs = qs.filter(has_department_scope=True, has_branch_scope=False)
        elif scope_type == "both":
            qs = qs.filter(has_branch_scope=True, has_department_scope=True)

        return qs

    @action(
        detail=False,
        methods=["delete"],
        url_path=r'(?P<user_id>\d+)/clear-scopes'
    )
    def clear_scopes(self, request, user_id=None):
        """
        Removes all matching HRBranchScope / HRDepartmentScope rows for the user.
        """
        try:
            target_id = int(user_id)
        except (TypeError, ValueError):
            return Response({"message": "Invalid user id"}, status=status.HTTP_400_BAD_REQUEST)

        scope_type = request.query_params.get("scope_type", "both").lower()
        deleted = {"branches": 0, "departments": 0}

        if scope_type in ("branch", "both"):
            # returns (count, per-model counts)
            deleted["branches"] = HRBranchScope.objects.filter(hr_user_id=target_id).delete()[0]

        if scope_type in ("department", "both"):
            deleted["departments"] = HRDepartmentScope.objects.filter(hr_user_id=target_id).delete()[0]

        return Response(
            {"hr_user": target_id, "deleted": deleted, "scope_type": scope_type},
            status=status.HTTP_200_OK
        )


class AttendanceExceptionViewSet(viewsets.ModelViewSet):
    """
    - Employees create exceptions with optional attachments (multipart)
    - Boss approves/rejects via actions
    - If rejected, an employee needs to submit an explanation letter (note)
    """
    serializer_class = AttendanceExceptionSerializer
    search_fields = ["reason__name", "employee__first_name", "employee__last_name"]
    ordering_fields = ["created_date"]
    ordering = ["-created_date"]
    filterset_class = AttendanceExceptionFilter
    # permission_classes = [HasDynamicPermission]
    # resource_key = "attendance.exceptions"
    # action_key_map = {"list": "list", "retrieve": "view", "approve": "approve", "reject": "reject"}
    CONSTANT = CONSTANTS.ATTENDANCE.EXCEPTION_STATUS

    def get_queryset(self):
        qs = (AttendanceException.objects
              .select_related("employee", "attendance", "reason", "expla")
              .prefetch_related("attachments", "approvals")
              .order_by("-created_date")
              )
        user = self.request.user

        # if self.action in ["list", "retrieve"]:
        #     scope = AttendanceExceptionListScope()
        #     return scope.filter_queryset(qs, user)

        # fallback: safest is own items only
        return qs.filter(Q(employee=user) | Q(manager=user) | Q(hr_user=user))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _decide_exception(self, request, pk, is_approved, status_response):
        obj = self.get_object()
        user = request.user

        approval_obj = obj.approvals.filter(user=user).first()
        if not approval_obj:
            raise ValidationError2(get_response_message(request, 700))

        if approval_obj.is_approved is not None:
            return Response({"message": "Already decided."}, status=400)

        ser = ApproveOrRejectExceptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        note = ser.validated_data.get("note")

        approval_obj.is_approved = is_approved
        approval_obj.decision_note = note
        approval_obj.user = user
        approval_obj.action_time = timezone.now()
        approval_obj.save(update_fields=["is_approved", "decision_note", "user", "action_time"])

        # Update main object's status
        if is_approved:
            obj.status = 'approved'
        else:
            obj.status = 'rejected'
        obj.save(update_fields=["status"])

        return Response({"status": status_response}, status=200)

    @action(detail=True,
            methods=["post"],
            url_path='approve',
            serializer_class=ApproveOrRejectExceptionSerializer)
    def approve(self, request, pk=None):
        return self._decide_exception(request, pk, True, "approved")

    @action(detail=True,
            methods=["post"],
            url_path='reject',
            serializer_class=ApproveOrRejectExceptionSerializer)
    def reject(self, request, pk=None):
        return self._decide_exception(request, pk, False, "rejected")
