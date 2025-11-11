import os

import requests
from django.db import transaction
from django.db.models import Prefetch, Q, OuterRef, Exists
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, mixins, views, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.company.models import Department, Company
from apps.core.filters import DepartmentManagerFilter
from apps.core.models import (
    PageRanking,
    SQLQuery,
    BranchManager,
    DepartmentManager,
)
from apps.core.serializers import (
    PageRankingSerializer,
    VerifyDGSISerializer,
    BranchManagerSerializer,
    DepartmentManagerSerializer,
    ManagersReorderSerializer,
    MoveToSerializer,
    ManagersSyncSerializer,
)
from apps.core.services import _normalize, _swap_with_neighbor, _move_to
from apps.docflow.serializers.docflow import SimpleResponseSerializer
from utils.constants import CONSTANTS
from utils.db_connection import django_connection, oracle_connection
from utils.exception import get_response_message, ValidationError2
from utils.tools import get_user_ip


class RatePageViewSet(viewsets.GenericViewSet,
                      mixins.CreateModelMixin,
                      mixins.ListModelMixin):
    queryset = PageRanking.objects.all()
    serializer_class = PageRankingSerializer


class SQLExecuteQueryView(views.APIView):
    query_type = openapi.Parameter('query_type', openapi.IN_QUERY,
                                   description="SQL Query type",
                                   type=openapi.TYPE_STRING, required=True)

    response = openapi.Response('response description', SimpleResponseSerializer)

    @swagger_auto_schema(manual_parameters=[query_type], responses={200: response})
    def get(self, request, *args, **kwargs):
        query_type = self.request.GET.get('query_type')

        try:
            query_obj = SQLQuery.objects.get(query_type=query_type)
            raw_sql = query_obj.sql_query
            required_params = query_obj.required_params or []
            conn = self.get_connection()

            with conn.cursor() as cursor:
                cursor.execute(raw_sql, required_params)

                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]

                if query_type == CONSTANTS.QUERY_TYPES.BY_AGES:
                    median_age = self.calculate_median_age(results)
                    return Response({'data': results, 'median_age': median_age})
                elif query_type == CONSTANTS.QUERY_TYPES.EMPLOYEE_EXPERIENCE:
                    median_experience = self.clean_and_calculate_median_experience(results)
                    return Response({'data': results, 'median_experience': median_experience})
                else:
                    return Response({'data': results})
        except SQLQuery.DoesNotExist:
            return Response({'message': 'Query not found'}, status=404)

    def get_connection(self):
        env = os.getenv('ENVIRONMENT')

        if env == 'DEV':
            conn = django_connection()
        else:
            conn = oracle_connection()

        return conn

    def calculate_median_age(self, data):
        # Step 1: Convert age groups into numerical bins
        cumulative_count = 0
        frequency_table = []

        for item in data:
            age_group = item["AGE_GROUP"]
            count = item["COUNT"]

            if "+" in age_group:  # Handle "50+" case
                lower_bound = int(age_group[:-1])  # Extract "50" from "50+"
                upper_bound = lower_bound + 10  # Assume a 10-year range for estimation
            else:
                lower_bound, upper_bound = map(int, age_group.split("-"))

            frequency_table.append({
                "lower": lower_bound,
                "upper": upper_bound,
                "count": count,
                "cumulative": cumulative_count
            })

            cumulative_count += count  # Update cumulative frequency

        # Step 2: Find the median class
        total_count = cumulative_count  # Sum of all counts
        median_position = total_count / 2

        for row in frequency_table:
            if row["cumulative"] + row["count"] >= median_position:
                median_class = row
                break

        # Step 3: Extract necessary values
        L = median_class["lower"]
        F = median_class["cumulative"]
        f = median_class["count"]
        h = median_class["upper"] - median_class["lower"]

        # Step 4: Apply the formula
        median_age = L + ((median_position - F) / f) * h
        return round(median_age)  # Round the result to the nearest whole number

    def clean_and_calculate_median_experience(self, data):
        """
        Cleans the experience data and calculates the median experience in years.
        """
        # Step 1: Define a mapping for categorical ranges
        category_mapping = {
            "До 3 месяцев": (0, 0.25),
            "От 3 до 12 месяцев": (0.25, 1),
            "От 1 года до 3 лет": (1, 3),
            "От 3 лет до 5 лет": (3, 5),
            "Более 5 лет": (5, 10)  # Assuming an upper bound of 10 years
        }

        # Step 2: Convert categories to structured numeric bins
        experience_bins = []
        for item in data:
            category = item["CATEGORY"]
            count = item["COUNT"]
            if category in category_mapping:
                lower, upper = category_mapping[category]
                experience_bins.append({"range": (lower, upper), "count": count})

        # Step 3: Calculate total count and find median position
        total_count = sum(item["count"] for item in experience_bins)
        median_position = total_count / 2

        # Step 4: Find the median class
        cumulative_count = 0
        median_class = None

        for item in experience_bins:
            lower, upper = item["range"]
            count = item["count"]

            if cumulative_count + count >= median_position:
                median_class = {"lower": lower, "upper": upper, "count": count, "cumulative": cumulative_count}
                break

            cumulative_count += count

        # Step 5: Apply the grouped median formula
        if not median_class:
            return None  # Safety check

        L = median_class["lower"]
        F = median_class["cumulative"]
        f = median_class["count"]
        h = median_class["upper"] - median_class["lower"]

        median_experience = L + ((median_position - F) / f) * h
        return round(median_experience, 1)  # Round to 1 decimal place


class EDSMobileVerifyView(generics.GenericAPIView):
    serializer_class = VerifyDGSISerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_id = serializer.validated_data.get('document_id')
        document = serializer.validated_data.get('document')
        user_ip = get_user_ip(request)
        header = {'X-Real-IP': user_ip, 'Host': os.getenv('E_IMZO_HOST')}
        url = 'http://127.0.0.1:8080/backend/mobile/verify'
        data = {'documentId': document_id, 'document': document}
        response = requests.post(url, data=data, headers=header)
        return Response(response.json())


class BranchManagerViewSet(viewsets.ModelViewSet):
    queryset = BranchManager.objects.select_related("user", "branch").order_by("sort_order", "id")
    serializer_class = BranchManagerSerializer
    search_fields = ("branch__name", "user__first_name", "user__last_name")
    filterset_fields = ("branch", "is_active")

    def list(self, request, *args, **kwargs):
        today = timezone.localdate()

        mgr_qs = (
            BranchManager.objects
            .filter(
                Q(is_active=True),
                Q(valid_from__isnull=True) | Q(valid_from__lte=today),
                Q(valid_until__isnull=True) | Q(valid_until__gte=today),
            )
            .select_related("user", "user__position", "user__status")
            .order_by("sort_order", "id")
        )

        branches = (
            Company.objects
            .filter(condition='A')
            .only("id", "name")
            .prefetch_related(Prefetch("manager_links", queryset=mgr_qs, to_attr="prefetched_managers"))
            .order_by("name")
        )

        # Optional filter by id
        branch_ids = request.query_params.get("branch")
        if branch_ids:
            branches = branches.filter(id__in=branch_ids)

        search = (request.query_params.get("search") or "").strip()
        if search:
            bm_match = (
                BranchManager.objects
                .filter(
                    branch_id=OuterRef("pk"),
                    is_active=True,
                )
                .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today))
                .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
                .filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__father_name__icontains=search)
                )
            )
            branches = branches.filter(
                Q(name__icontains=search) | Exists(bm_match)
            )

        def order_details(link):
            return {
                "id": link.id,
                "is_primary": link.is_primary,
                "is_active": link.is_active,
                "sort_order": link.sort_order,
                "valid_from": link.valid_from,
                "valid_until": link.valid_until,
            }

        def user_payload(link):
            u = link.user
            if not u:
                return None
            pos = getattr(u, "position", None)
            sts = getattr(u, "status", None)
            return {
                "id": u.id,
                "full_name": getattr(u, "full_name", None),
                "first_name": getattr(u, "first_name", None),
                "last_name": getattr(u, "last_name", None),
                "father_name": getattr(u, "father_name", None),
                "color": getattr(u, "color", None),
                "order_details": order_details(link),
                "position": {"id": getattr(pos, "id", None), "name": getattr(pos, "name", None)} if pos else None,
                "status": {"id": getattr(sts, "id", None), "name": getattr(sts, "name", None),
                           "code": getattr(sts, "code", None)} if sts else None,
            }

        items = []
        for br in branches:
            managers = getattr(br, "prefetched_managers", []) or []
            # if not managers:
            #     continue
            leader = next((m for m in managers if m.is_primary), None)
            assistants = [m for m in managers if not m.is_primary]
            items.append({
                "branch": {"id": br.id, "name": br.name},
                "leader": user_payload(leader) if leader else None,
                "assistants": [user_payload(m) for m in assistants if m.user_id],
            })

        page = self.paginate_queryset(items)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(items)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    @action(detail=False,
            methods=["post"],
            url_path="sync",
            serializer_class=ManagersSyncSerializer)
    def sync(self, request):
        """
        POST /managers/branch/sync/
        {
          "object_id": 12,             # branch_id
          "managers_ids": [102, 219]   # first = leader, others = deputies in order
        }
        """
        ser = ManagersSyncSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        branch_id = ser.validated_data["object_id"]
        user_ids = ser.validated_data["managers_ids"]

        # Lock all links for this branch
        scope = BranchManager.objects.select_for_update().filter(branch_id=branch_id)

        existing = list(scope)
        by_user = {m.user_id: m for m in existing if m.user_id}

        # 1) delete links whose users are not in submitted list
        keep_ids = set(user_ids)
        to_delete = [m.id for m in existing if (m.user_id not in keep_ids)]
        if to_delete:
            BranchManager.objects.filter(id__in=to_delete).delete()

        # 2) ensure leader & deputies exist and are updated
        leader_uid = user_ids[0] if user_ids else None
        deputies_uids = user_ids[1:] if user_ids else []
        deputy_order = {uid: idx for idx, uid in enumerate(deputies_uids)}  # 0..n-1

        changed = []
        created = 0

        # leader
        if leader_uid is not None:
            m = by_user.get(leader_uid)
            if m is None:
                m = BranchManager(branch_id=branch_id, user_id=leader_uid, is_primary=True, is_active=True,
                                  sort_order=0)
                m.save()
                created += 1
            else:
                # ensure it's primary
                if not m.is_primary or not m.is_active:
                    m.is_primary = True
                    m.is_active = True
                    changed.append(m)

        # deputies
        for uid in deputies_uids:
            m = by_user.get(uid)
            if m is None:
                m = BranchManager(branch_id=branch_id,
                                  user_id=uid,
                                  is_primary=False,
                                  is_active=True,
                                  sort_order=deputy_order[uid])
                m.save()
                created += 1
            else:
                wanted_so = deputy_order[uid]
                needs = (m.is_primary or m.sort_order != wanted_so or not m.is_active)
                if needs:
                    m.is_primary = False
                    m.sort_order = wanted_so
                    m.is_active = True
                    changed.append(m)

        if changed:
            BranchManager.objects.bulk_update(changed, ["is_primary", "sort_order", "is_active"])

        # 3) enforce single primary: unset all others if leader is present
        if leader_uid is not None:
            scope.exclude(user_id=leader_uid).update(is_primary=False)
        else:
            # no leaders submitted: ensure no row is primary
            scope.update(is_primary=False)

        # 4) normalize deputy ordering (0..n-1)
        _normalize(self._scope_qs(branch_id, is_primary=False))

        return Response(
            {
                "branch_id": branch_id,
                "created": created,
                "deleted": len(to_delete),
                "leader_user_id": leader_uid,
                "deputies": deputies_uids
            },
            status=status.HTTP_200_OK
        )

    def _scope_qs(self, obj_or_branch_id, is_primary=None):
        branch_id = obj_or_branch_id.branch_id if isinstance(obj_or_branch_id, BranchManager) else int(obj_or_branch_id)
        qs = BranchManager.objects.filter(branch_id=branch_id)
        if is_primary is not None:
            qs = qs.filter(is_primary=is_primary)
        return qs

    @transaction.atomic
    def perform_destroy(self, instance):
        scope = self._scope_qs(instance)
        instance.delete()
        _normalize(scope)

    @action(detail=False, methods=["delete"], url_path=r"delete-by/(?P<branch_id>\d+)")
    def delete_by(self, request, branch_id=None):
        """
        DELETE /department-managers/delete-by/{branch_id}/
        """

        try:
            branch = Company.objects.get(id=branch_id)
            if branch.condition == 'A':
                message = get_response_message(request, 898)
                raise ValidationError2(message)
        except Company.DoesNotExist:
            return Response(status=404, data={"message": "Branch not found."})

        try:
            objs = BranchManager.objects.filter(branch_id=branch_id)
        except DepartmentManager.DoesNotExist:
            return Response(status=204)
        objs.delete()
        return Response(status=204)

    @action(detail=True,
            methods=["post"],
            url_path="activate",
            serializer_class=ManagersReorderSerializer)
    def activate(self, request, pk=None):
        obj = self.get_object()
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active"])
        return Response({"id": obj.id, "is_active": obj.is_active})

    @action(detail=True,
            methods=["post"],
            url_path="deactivate",
            serializer_class=ManagersReorderSerializer)
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active"])
        return Response({"id": obj.id, "is_active": obj.is_active})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-up",
            serializer_class=ManagersReorderSerializer)
    def move_up(self, request, pk=None):
        obj = self.get_object()
        _swap_with_neighbor(self._scope_qs(obj), obj, "up")
        return Response({"message": "moved up"})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-down",
            serializer_class=ManagersReorderSerializer)
    def move_down(self, request, pk=None):
        obj = self.get_object()
        _swap_with_neighbor(self._scope_qs(obj), obj, "down")
        return Response({"message": "moved down"})

    @transaction.atomic
    @action(detail=False,
            methods=["post"],
            url_path="reorder",
            serializer_class=ManagersReorderSerializer)
    def reorder(self, request):
        """
        POST /branch-managers/reorder/
        { "object_id": 12,
          "ids": [5, 9, 3, 7]
        }
        # top -> bottom
        """
        ser = ManagersReorderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        branch = ser.validated_data["object_id"]
        ids = ser.validated_data["ids"]

        scope = self._scope_qs(branch).select_for_update()
        scope_ids = set(scope.values_list("id", flat=True))
        if set(ids) - scope_ids:
            return Response({"message": "ids contain items outside this branch scope"}, status=400)

        order_map = {pk: i for i, pk in enumerate(ids)}  # top=0
        objects = list(scope)
        for o in objects:
            new_so = order_map.get(o.id)
            if new_so is not None and o.sort_order != new_so:
                o.sort_order = new_so
        BranchManager.objects.bulk_update(objects, ["sort_order"])
        return Response({"message": "reordered", "count": len(objects)})

    # Optional: ensure one primary per branch
    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="set-primary",
            serializer_class=ManagersReorderSerializer)
    def set_primary(self, request, pk=None):
        obj = self.get_object()
        scope = self._scope_qs(obj).select_for_update()
        scope.exclude(pk=obj.pk).update(is_primary=False)
        if not obj.is_primary:
            obj.is_primary = True
            obj.save(update_fields=["is_primary"])
        return Response({"id": obj.id, "is_primary": obj.is_primary})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-to",
            serializer_class=MoveToSerializer)
    def move_to(self, request, pk=None):
        """
        POST /managers/department/{id}/move-to/
        { "position": 2 }  # 0-based index, top = 0
        """
        obj = self.get_object()
        ser = MoveToSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target = ser.validated_data["position"]
        _move_to(self._scope_qs(obj), obj, target)
        return Response({"message": "moved", "id": obj.id, "position": target}, status=status.HTTP_200_OK)


class DepartmentManagerViewSet(viewsets.ModelViewSet):
    queryset = (DepartmentManager.objects
                .select_related("user", "department")
                .order_by("sort_order", "id"))
    serializer_class = DepartmentManagerSerializer
    search_fields = ("department__name", "user__first_name", "user__last_name")
    filterset_class = DepartmentManagerFilter

    def list(self, request, *args, **kwargs):
        today = timezone.localdate()

        # Prefetch managers: only current & active; no N+1 for user/position/status
        mgr_qs = (
            DepartmentManager.objects
            .filter(
                Q(is_active=True),
                Q(valid_from__isnull=True) | Q(valid_from__lte=today),
                Q(valid_until__isnull=True) | Q(valid_until__gte=today),
            )
            .select_related("user", "user__position", "user__status", "department")
            .order_by("sort_order", "id")  # top first
        )

        departments = (
            Department.objects
            .filter(parent__isnull=True, condition__in=('A', 'K'))
            .prefetch_related(Prefetch("manager_links", queryset=mgr_qs, to_attr="prefetched_managers"))
            .only("id", "name")
            .order_by("name")
        )

        # Filter: ?department=1
        dept_id = request.query_params.get("department")
        if dept_id:
            departments = departments.filter(id=int(dept_id))

        company_id = request.query_params.get("company")
        if company_id:
            departments = departments.filter(company_id=int(company_id))

        # Filter: ?search={user name or department name}
        search = (request.query_params.get("search") or "").strip()
        if search:
            # Subquery: current managers for this department matching user name
            dm_match = (
                DepartmentManager.objects
                .filter(
                    department_id=OuterRef("pk"),
                    is_active=True,
                )
                .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today))
                .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
                .filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__father_name__icontains=search)
                )
            )
            departments = departments.filter(
                Q(name__icontains=search) | Exists(dm_match)
            )

        def order_details(link):
            return {
                "id": link.id,
                "is_primary": link.is_primary,
                "is_active": link.is_active,
                "sort_order": link.sort_order,
                "valid_from": link.valid_from,
                "valid_until": link.valid_until,
            }

        def user_payload(link):
            u = link.user
            if not u:
                return None
            pos = getattr(u, "position", None)
            sts = getattr(u, "status", None)
            return {
                "id": u.id,
                "full_name": getattr(u, "full_name", None),
                "first_name": getattr(u, "first_name", None),
                "last_name": getattr(u, "last_name", None),
                "father_name": getattr(u, "father_name", None),
                "color": getattr(u, "color", None),
                "order_details": order_details(link),
                "position": {"id": getattr(pos, "id", None), "name": getattr(pos, "name", None)} if pos else None,
                "status": {"id": getattr(sts, "id", None), "name": getattr(sts, "name", None),
                           "code": getattr(sts, "code", None)} if sts else None,
            }

        items = []
        for dept in departments:
            managers = getattr(dept, "prefetched_managers", []) or []
            # if not managers:
            # Skip empty departments; or include with leader=None, assistants=[]
            # continue

            leader_link = next((m for m in managers if m.is_primary), None)
            assistants_links = [m for m in managers if not m.is_primary]

            item = {
                "department": {"id": dept.id, "name": dept.name},
                "leader": user_payload(leader_link) if leader_link else None,
                "assistants": [user_payload(m) for m in assistants_links if m.user_id],
            }
            items.append(item)

        page = self.paginate_queryset(items)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(items)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        """
        POST /department-managers/sync/
        {
          "object_id": 9,                 # department_id
          "managers_ids": [102, 219, 220] # first = leader, others = deputies in order
        }
        """
        ser = ManagersSyncSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dept_id = ser.validated_data["object_id"]
        user_ids = ser.validated_data["managers_ids"]

        scope = DepartmentManager.objects.select_for_update().filter(department_id=dept_id)

        existing = list(scope)
        by_user = {m.user_id: m for m in existing if m.user_id}

        # delete extras
        keep_ids = set(user_ids)
        to_delete = [m.id for m in existing if (m.user_id not in keep_ids)]
        if to_delete:
            DepartmentManager.objects.filter(id__in=to_delete).delete()

        # desired shape
        leader_uid = user_ids[0] if user_ids else None
        deputies_uids = user_ids[1:] if user_ids else []
        deputy_order = {uid: idx for idx, uid in enumerate(deputies_uids)}

        changed = []
        created = 0

        # leader
        if leader_uid is not None:
            m = by_user.get(leader_uid)
            if m is None:
                m = DepartmentManager(department_id=dept_id, user_id=leader_uid, is_primary=True, is_active=True,
                                      sort_order=0)
                m.save()
                created += 1
            else:
                if not m.is_primary or not m.is_active:
                    m.is_primary = True
                    m.is_active = True
                    changed.append(m)

        # deputies
        for uid in deputies_uids:
            m = by_user.get(uid)
            if m is None:
                m = DepartmentManager(department_id=dept_id, user_id=uid, is_primary=False, is_active=True,
                                      sort_order=deputy_order[uid])
                m.save()
                created += 1
            else:
                wanted_so = deputy_order[uid]
                needs = (m.is_primary or m.sort_order != wanted_so or not m.is_active)
                if needs:
                    m.is_primary = False
                    m.sort_order = wanted_so
                    m.is_active = True
                    changed.append(m)

        if changed:
            DepartmentManager.objects.bulk_update(changed, ["is_primary", "sort_order", "is_active"])

        # single primary guarantee
        if leader_uid is not None:
            scope.exclude(user_id=leader_uid).update(is_primary=False)
        else:
            scope.update(is_primary=False)

        # normalize deputies
        _normalize(self._scope_qs(dept_id, is_primary=False))

        return Response(
            {"department_id": dept_id, "created": created, "deleted": len(to_delete), "leader_user_id": leader_uid,
             "deputies": deputies_uids},
            status=status.HTTP_200_OK
        )

    def _scope_qs(self, obj_or_department_id, is_primary=None):
        department_id = obj_or_department_id.department_id if isinstance(obj_or_department_id,
                                                                         DepartmentManager) else int(
            obj_or_department_id)
        qs = DepartmentManager.objects.filter(department_id=department_id)

        if is_primary is not None:
            qs = qs.filter(is_primary=is_primary)
        return qs

    @transaction.atomic
    def perform_destroy(self, instance):
        scope = self._scope_qs(instance)
        instance.delete()
        _normalize(scope)

    @action(detail=False, methods=["delete"], url_path=r"delete-by/(?P<department_id>\d+)")
    def delete_by(self, request, department_id=None):
        """
        DELETE /department-managers/delete-by/{department_id}/
        """

        # Check if Department status is not 'A' or 'K'
        try:
            department = Department.objects.get(id=department_id)
            if department.condition in ('A', 'K'):
                message = get_response_message(request, 897)
                raise ValidationError2(message)
        except Department.DoesNotExist:
            return Response(status=404, data={"message": "Department not found."})

        try:
            objs = DepartmentManager.objects.filter(department_id=department_id)
        except DepartmentManager.DoesNotExist:
            return Response(status=204)
        objs.delete()
        return Response(status=204)

    @action(detail=True,
            methods=["post"],
            url_path="activate",
            serializer_class=ManagersReorderSerializer)
    def activate(self, request, pk=None):
        obj = self.get_object()
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active"])
        return Response({"id": obj.id, "is_active": obj.is_active})

    @action(detail=True,
            methods=["post"],
            url_path="deactivate",
            serializer_class=ManagersReorderSerializer)
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active"])
        return Response({"id": obj.id, "is_active": obj.is_active})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-up",
            serializer_class=ManagersReorderSerializer)
    def move_up(self, request, pk=None):
        obj = self.get_object()
        _swap_with_neighbor(self._scope_qs(obj), obj, "up")
        return Response({"message": "moved up"})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-down",
            serializer_class=ManagersReorderSerializer)
    def move_down(self, request, pk=None):
        obj = self.get_object()
        _swap_with_neighbor(self._scope_qs(obj), obj, "down")
        return Response({"message": "moved down"})

    @transaction.atomic
    @action(detail=False,
            methods=["post"],
            url_path="reorder",
            serializer_class=ManagersReorderSerializer)
    def reorder(self, request):
        """
        POST /department-managers/reorder/
        { "object_id": 34, "ids": [2, 6, 4] }  # top -> bottom
        """
        ser = ManagersReorderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        department = ser.validated_data["object_id"]
        ids = ser.validated_data["ids"]

        scope = self._scope_qs(department).select_for_update()
        scope_ids = set(scope.values_list("id", flat=True))
        if set(ids) - scope_ids:
            return Response({"message": "ids contain items outside this department scope"}, status=400)

        order_map = {pk: i for i, pk in enumerate(ids)}  # top=0
        objects = list(scope)
        for o in objects:
            new_so = order_map.get(o.id)
            if new_so is not None and o.sort_order != new_so:
                o.sort_order = new_so
        DepartmentManager.objects.bulk_update(objects, ["sort_order"])
        return Response({"message": "reordered", "count": len(objects)})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="set-primary",
            serializer_class=ManagersReorderSerializer)
    def set_primary(self, request, pk=None):
        obj = self.get_object()
        scope = self._scope_qs(obj).select_for_update()
        scope.exclude(pk=obj.pk).update(is_primary=False)
        if not obj.is_primary:
            obj.is_primary = True
            obj.save(update_fields=["is_primary"])
        return Response({"id": obj.id, "is_primary": obj.is_primary})

    @transaction.atomic
    @action(detail=True,
            methods=["post"],
            url_path="move-to",
            serializer_class=MoveToSerializer)
    def move_to(self, request, pk=None):
        """
        POST /managers/department/{id}/move-to/
        { "position": 2 } 0-based index, top = 0
        """
        obj = self.get_object()
        ser = MoveToSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target = ser.validated_data["position"]
        _move_to(self._scope_qs(obj), obj, target)
        return Response({"message": "moved", "id": obj.id, "position": target}, status=status.HTTP_200_OK)
