from django.db.models import Q
from django.utils import translation
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.company.filters import DepartmentFilters, CompanyFilters
from apps.company.models import Company, Position, Department
from apps.company.serializers import (
    CompanySerializer,
    DepartmentActiveOrInactiveSerializer,
    DepartmentSerializer,
    DepartmentUserSerializer,
    DepartmentWithoutChildSerializer,
    PositionSerializer,
    SubDepartmentSerializer,
    DepartmentWithUserSerializer
)
from apps.company.tasks import recalculate_sub_department_count
from apps.user.models import User
from utils.exception import get_response_message
from utils.tools import get_or_none, get_children


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().order_by('created_date')
    serializer_class = CompanySerializer
    search_fields = ('name',)
    filterset_class = CompanyFilters


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    search_fields = ('name', 'name_uz', 'name_ru')
    filterset_fields = ('is_active',)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('company', 'parent__parent').prefetch_related(
        'children').filter(parent__isnull=True)
    serializer_class = DepartmentSerializer
    search_fields = ('name',)
    filterset_class = DepartmentFilters

    def get_object(self):
        queryset = Department.objects.filter()

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    @action(methods=['put'], detail=True, url_path='add-users', url_name='add_users',
            serializer_class=DepartmentUserSerializer)
    def add_users(self, request, pk=None, *args, **kwargs):
        """
        Sets users to department.
        Request body should be in array format like this:
        [
            {
                "user_id": 1
            },
            {
                "user_id": 2
            }
        ]
        """
        instance = self.get_object()
        serializer = DepartmentUserSerializer(instance, data=request.data, many=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        users = serializer.validated_data
        for obj in users:
            user = get_or_none(User, request, id=obj.get('user_id'))
            user.department = instance
            user.save()

        msg = get_response_message(request, 803)
        return Response(msg)

    @action(methods=['put'], detail=True, url_path='make-active-or-inactive', url_name='make_active_or_inactive',
            serializer_class=DepartmentActiveOrInactiveSerializer)
    def make_active_or_inactive(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        serializer = DepartmentActiveOrInactiveSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        condition = serializer.validated_data.get('condition')
        if condition in ['a', 'A']:
            instance.condition = 'A'
            instance.save()
        elif condition in ['p', 'P']:
            if instance.children.filter(condition='A').count() > 0:
                msg = get_response_message(request, 620)
                return Response(msg, status=status.HTTP_400_BAD_REQUEST)

            users = User.objects.filter(department_id=instance.id)
            if users.count() > 0:
                msg = get_response_message(request, 621)
                return Response(msg, status=status.HTTP_400_BAD_REQUEST)

            instance.condition = 'P'
            instance.save()
        return Response(serializer.data)

    @action(methods=['get'], detail=False,
            url_name='sub_department',
            url_path='sub-departments/(?P<department_id>[^/.]+)',
            serializer_class=DepartmentSerializer)
    def sub_department(self, request, department_id=None, *args, **kwargs):
        # Create an initial query to retrieve departments
        query = Department.objects.filter()

        # Check if the client's preferred language is available and activate translation if so.
        if 'HTTP_ACCEPT_LANGUAGE' in self.request.META:
            language = self.request.META['HTTP_ACCEPT_LANGUAGE']
            translation.activate(language)

        query = query.filter(parent_id=department_id)
        queryset = self.filter_queryset(query)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubDepartmentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SubDepartmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=False, url_name='top-level-department', url_path='top-level-departments',
            serializer_class=DepartmentWithoutChildSerializer)
    def department_without_children(self, request, *args, **kwargs):
        query = self.get_queryset().select_related('company').filter(parent__isnull=True)
        queryset = self.filter_queryset(query)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DepartmentWithoutChildSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = DepartmentWithoutChildSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['put'], detail=True, url_path='recalculate-sub-department-count')
    def recalculate_sub_department_count(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        # list_of_children = get_children(Department, instance.id)
        # instance.sub_department_count = len(list_of_children)
        # instance.save()
        recalculate_sub_department_count(instance.id)
        return Response({'message': 'success'})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.children.count() > 0:
            msg = get_response_message(request, 620)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(department_id=instance.id)
        if users.count() > 0:
            msg = get_response_message(request, 621)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        self.perform_destroy(instance)
        if instance.parent:
            recalculate_sub_department_count(instance.parent_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DepartmentWithUsersViewSet(viewsets.GenericViewSet,
                                 mixins.ListModelMixin,
                                 mixins.RetrieveModelMixin):
    queryset = Department.objects.select_related('company', 'parent').prefetch_related('children').filter(
        parent__isnull=True, condition='A')
    serializer_class = DepartmentWithUserSerializer
    filterset_class = DepartmentFilters
    search_fields = (
        'name',
        'employees__first_name',
        'employees__last_name',
        'employees__father_name',
        'employees__normalized_cisco',
    )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Get the search term from the request
        search = self.request.query_params.get('search', None)
        if search:
            # Filter the queryset based on the search term in employees fields
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(employees__first_name__icontains=search) |
                Q(employees__last_name__icontains=search) |
                Q(employees__father_name__icontains=search) |
                Q(employees__normalized_cisco__icontains=search)
            ).distinct()

        return queryset
