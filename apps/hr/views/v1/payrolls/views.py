import datetime

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hr.filters import PayrollPeriodFilter
from apps.hr.models import PayrollPeriod, PayrollApproval, PayrollCell, PayrollRow
from apps.hr.serializers.v1.payrolls import PayrollPeriodCreateSerializer, PayrollPeriodListSerializer
from apps.hr.serializers.v1.payrolls.payroll import PayrollPeriodReadSerializer, PayrollApproveSerializer
from apps.hr.services.calendar import last_day_of_month, choose_mid_pay_date
from apps.hr.services.payroll_generator import upsert_cells_for_date
from utils.constants import CONSTANTS


class PayrollPeriodViewSet(mixins.RetrieveModelMixin,
                           mixins.ListModelMixin,
                           viewsets.GenericViewSet):
    queryset = (PayrollPeriod.objects
                .select_related("company", "department")
                .prefetch_related("rows__cells", "approvals"))
    serializer_class = PayrollPeriodListSerializer
    filterset_class = PayrollPeriodFilter
    search_fields = ["company__name", "department__name", "company__local_code", "department__code"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PayrollPeriodReadSerializer
        elif self.action == "generate":
            return PayrollPeriodCreateSerializer
        elif self.action == "approve":
            return PayrollApproveSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["post"], serializer_class=PayrollPeriodCreateSerializer)
    def generate(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        date = serializer.validated_data["date"]
        upsert_cells_for_date(target_date=date)
        return Response({"status": "Payroll data generated for date {}".format(date)})

    @action(methods=["post"],
            detail=False,
            serializer_class=PayrollApproveSerializer,
            url_path="approve")
    def approve(self, request):
        """
        Body:
        {
          "ids": [1,2,3],
          "approved": true|false,
          "note": "ok",
          "window": "mid" | "final"
        }
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = list(dict.fromkeys(ser.validated_data["ids"]))
        approved = bool(ser.validated_data["approved"])
        note = ser.validated_data.get("note") or ""
        window = ser.validated_data["window"]  # "mid" or "final"
        now = timezone.now()
        user = request.user
        STS = CONSTANTS.ATTENDANCE.PAYROLL_STATUS

        with transaction.atomic():
            # Lock rows & fetch current states
            periods_qs = PayrollPeriod.objects.select_for_update().filter(id__in=ids)
            found_ids = set(periods_qs.values_list("id", flat=True))
            missing = [i for i in ids if i not in found_ids]
            if missing:
                return Response({"message": "Some IDs not found.", "missing": missing},
                                status=status.HTTP_400_BAD_REQUEST)

            # Only periods in review can be decided
            not_in_review = list(periods_qs.exclude(status=STS.IN_REVIEW).values_list("id", flat=True))
            if not_in_review:
                return Response(
                    {
                        "message": "Only 'in_review' periods can be approved/rejected.",
                        "invalid": not_in_review
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Window pre-checks
            invalid_window_state = []
            already_locked = []
            for p in periods_qs:
                if window == "mid":
                    if p.mid_locked:
                        already_locked.append(p.id)
                    # Optional guard: if final already locked, block
                    if p.final_locked:
                        invalid_window_state.append(p.id)
                else:  # final
                    if not p.mid_locked:
                        invalid_window_state.append(p.id)  # can't finalize before mid window locked
                    if p.final_locked:
                        already_locked.append(p.id)

            if invalid_window_state:
                return Response(
                    {
                        "message": f"Invalid window state for '{window}' decision.",
                        "invalid": invalid_window_state
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            results = []

            # Proceed; allow idempotent replay on "already_locked" by short-circuiting updates
            for period in periods_qs:
                # If window already locked, just echo current status (idempotent)
                if (window == "mid" and period.mid_locked) or (window == "final" and period.final_locked):
                    results.append({
                        "id": period.id,
                        "status": period.status,
                        "skipped": "already_locked"
                    })
                    continue

                # Record/overwrite this user's decision (per-period aggregate;
                PayrollApproval.objects.update_or_create(
                    period=period,
                    user=user,
                    defaults={
                        "decided": True,
                        "approved": approved,
                        "note": note,
                        "decided_at": now,
                    },
                )

                # Window locking + status progression
                if window == "mid":
                    period.mid_locked = True
                    period.mid_approved_at = now
                    # Status after mid:
                    #  - approved mid => keep IN_REVIEW (final still ahead)
                    #  - rejected mid => whole period REJECTED
                    next_status = STS.IN_REVIEW if approved else STS.REJECTED
                    # Note: do NOT change final_* here

                    if period.status != next_status:
                        period.status = next_status

                    period.save(update_fields=[
                        "status", "mid_locked", "mid_approved_at", "modified_date"
                    ])

                else:  # window == "final"
                    period.final_locked = True
                    period.final_approved_at = now
                    # Status after final:
                    #  - approved final => APPROVED
                    #  - rejected final => REJECTED
                    next_status = STS.APPROVED if approved else STS.REJECTED
                    if period.status != next_status:
                        period.status = next_status

                    period.save(update_fields=[
                        "status", "final_locked", "final_approved_at", "modified_date"
                    ])

                results.append({"id": period.id, "status": period.status})

        # Optionally include lists for transparency
        payload = {"updated": results}
        if already_locked:
            payload["already_locked"] = already_locked
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="send-to-review")
    def send_to_review(self, request, pk=None):
        """
        Transition a PayrollPeriod to 'in_review' status.
        """
        period = self.get_object()
        STS = CONSTANTS.ATTENDANCE.PAYROLL_STATUS

        if period.status not in [STS.DRAFT, STS.REJECTED]:
            return Response(
                {
                    "message": "Only 'draft' or 'rejected' periods can be sent to review.",
                    "current_status": period.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        period.status = STS.IN_REVIEW
        period.save(update_fields=["status", "modified_date"])

        return Response({"id": period.id, "new_status": period.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def subtotal(self, request, pk=None):
        """
        Returns total hours per employee for mid/final payout windows.
        """
        period = self.get_object()
        kind = (request.query_params.get("kind") or "mid").lower()
        y, m = period.year, period.month

        # compute mid/final windows based on your calendar helpers
        mid = choose_mid_pay_date(y, m)
        if kind == "final":
            start = mid + datetime.timedelta(days=1)
            end = datetime.date(y, m, last_day_of_month(y, m))
        else:  # mid
            start = datetime.date(y, m, 1)
            end = mid

        items = (PayrollCell.objects
                 .filter(row__period=period, date__range=(start, end))
                 .values("row__employee_id")
                 .annotate(hours=Sum("hours"))
                 .order_by("row__employee_id"))

        return Response({
            "period_id": period.id,
            "company_id": period.company_id,
            "year": y, "month": m,
            "kind": kind,
            "start": str(start), "end": str(end),
            "items": [{"employee_id": r["row__employee_id"], "hours": r["hours"] or 0} for r in items],
        })

    @action(detail=True, methods=["get"])
    def grid(self, request, pk=None):
        """
        Compact matrix for fast rendering:
        days: ["2025-11-01", ...]
        rows: [{ employee, full_name, codes: ["", "8", "0", "VACATION", ...] }]
        """
        period = self.get_object()
        y, m = period.year, period.month

        # choose range
        rng = (request.query_params.get("range") or "full").lower()
        mid = choose_mid_pay_date(y, m)
        first = datetime.date(y, m, 1)
        last = datetime.date(y, m, last_day_of_month(y, m))
        if rng == "mid":
            start, end = first, mid
        elif rng == "final":
            start, end = mid + datetime.timedelta(days=1), last
        else:
            start, end = first, last

        # build day index
        days = []
        d = start
        while d <= end:
            days.append(d)
            d += datetime.timedelta(days=1)
        day_index = {d: i for i, d in enumerate(days)}

        # initialize rows
        out_rows = []
        row_map = {}  # employee_id -> index in out_rows

        # prefetch rows minimal
        pr_qs = (PayrollRow.objects
                 .filter(period=period)
                 .values("id", "employee_id", "department_id"))
        for r in pr_qs:
            codes = [""] * len(days)
            out_rows.append({
                "employee": r["employee_id"],
                "department": r["department_id"],
                "codes": codes,
            })
            row_map[r["id"]] = len(out_rows) - 1

        # fill codes
        for c in (PayrollCell.objects
                .filter(row__period=period, date__range=(start, end))
                .values("row_id", "date", "code")):
            i = row_map.get(c["row_id"])
            j = day_index.get(c["date"])
            if i is not None and j is not None:
                out_rows[i]["codes"][j] = c["code"]

        return Response({
            "period_id": period.id,
            "company_id": period.company_id,
            "year": y, "month": m,
            "range": rng,
            "days": [d.isoformat() for d in days],
            "rows": out_rows,
        })
