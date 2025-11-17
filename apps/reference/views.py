from collections import OrderedDict

from django.db.models import Q
from rest_framework import viewsets, status, mixins, views
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.policy.permissions import HasDynamicPermission
from apps.reference.filters import RegionFilters, CountryFilters
from apps.reference.models import (
    ActionModel,
    CommentModel,
    Correspondent,
    DeliveryType,
    District,
    DocumentSubType,
    DocumentTitle,
    DocumentType,
    EmployeeGroup,
    ExpenseType,
    Journal,
    LanguageModel,
    Priority,
    Region,
    ShortDescription,
    StatusModel, Country, AppVersion, CityDistance, AttendanceReason, ExceptionEmployee,
)
from apps.reference.serializers import (
    ActionModelSerializer,
    CommentSerializer,
    CorrespondentSerializer,
    DeliveryTypeSerializer,
    DistrictSerializer,
    DocumentSubTypeSerializer,
    DocumentTitleSerializer,
    DocumentTypeSerializer,
    EmployeeGroupSerializer,
    ExpenseTypeSerializer,
    JournalActivateOrDeactivateSerializer,
    JournalChangeSortingSerializer,
    JournalSerializer,
    LanguageModelSerializer,
    PrioritySerializer,
    RegionSerializer,
    ShortDescriptionSerializer,
    StatusModelSerializer, CountrySerializer, AppVersionSerializer, CityDistanceSerializer,
    AttendanceReasonSerializer, ExceptionEmployeeSerializer,
)
from config.middlewares.current_user import get_current_user_id
from utils.exception import get_response_message


class CommentViewSet(viewsets.ModelViewSet):
    queryset = CommentModel.objects.filter(replied_to__isnull=True, is_deleted=False).order_by('created_date')
    serializer_class = CommentSerializer
    filterset_fields = ('object_id', 'content_type')

    def get_queryset(self):
        q = super().get_queryset().filter(replied_to__isnull=True, is_deleted=False)
        object_id = self.request.query_params.get('object_id', None)
        content_type = self.request.query_params.get('content_type', None)

        if object_id is not None and content_type is not None:
            q = q.filter(object_id=object_id, content_type=content_type)
        else:
            q = q.filter(created_by_id=get_current_user_id())
        return q.order_by('created_date')

    def get_object(self):
        queryset = CommentModel.objects.filter(created_by_id=self.request.user.id)

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

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop('pop', False)
        if instance.created_by_id == get_current_user_id():
            serializer = CommentSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.created_by_id == get_current_user_id():
            instance.is_deleted = True
            instance.save()

            message = get_response_message(request, 801)
            message['message'] = message['message'].format(object='Comment')
            return Response(message, status=status.HTTP_200_OK)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)


class StatusModelViewSet(viewsets.ModelViewSet):
    queryset = StatusModel.objects.all()
    serializer_class = StatusModelSerializer
    filterset_fields = ['name', 'description', 'group']
    search_fields = ['name', 'description', ]
    ordering = ['name', ]


class CorrespondentViewSet(viewsets.ModelViewSet):
    queryset = Correspondent.objects.all()
    serializer_class = CorrespondentSerializer
    filterset_fields = ['type', 'tin']
    search_fields = ['name', 'tin', 'legal_name', 'first_name', 'last_name', 'father_name']

    # resource_key = 'reference.correspondent'
    # action_key_map = {
    # "list": "list",
    #     "retrieve": "view",
    #     "create": "create",
    #     "update": "update",
    #     "partial_update": "update",
    #     "destroy": "delete",
    # }
    # permission_classes = [HasDynamicPermission]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentTitleViewSet(viewsets.ModelViewSet):
    queryset = DocumentTitle.objects.all()
    serializer_class = DocumentTitleSerializer
    filterset_fields = ['name', 'is_active']
    search_fields = ['name', ]
    ordering = ['name', ]


class EmployeeGroupViewSet(viewsets.ModelViewSet):
    queryset = EmployeeGroup.objects.all()
    serializer_class = EmployeeGroupSerializer
    filterset_fields = ['name', ]
    search_fields = ['name', ]
    ordering = ['name', ]

    def get_queryset(self):
        queryset = super(EmployeeGroupViewSet, self).get_queryset()
        return queryset.prefetch_related('employees').filter(created_by_id=get_current_user_id())


class ShortDescriptionViewSet(viewsets.ModelViewSet):
    queryset = ShortDescription.objects.order_by('-created_date')
    serializer_class = ShortDescriptionSerializer
    search_fields = ['title', 'description', ]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.created_by_id != get_current_user_id():
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActionModelViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = ActionModel.objects.order_by('created_date')
    serializer_class = ActionModelSerializer
    filterset_fields = ['object_id', 'content_type']


class JournalViewSet(viewsets.ModelViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    search_fields = ('name', 'name_uz', 'name_ru')
    filterset_fields = ('is_for_compose', 'code')
    ordering = ['sort_order', ]

    @action(detail=True, methods=['put'], url_path='change-order', url_name='change_order',
            serializer_class=JournalChangeSortingSerializer)
    def change_order(self, request, pk=None):
        instance = self.get_object()
        serializer = JournalChangeSortingSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        sort_order = serializer.validated_data.get('sort_order')
        old_sort_order = instance.sort_order
        journal = Journal.objects.filter(sort_order=sort_order).first()
        if journal:
            journal.sort_order = old_sort_order
            journal.save()
        instance.sort_order = sort_order
        instance.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'], url_path='activate-or-deactivate', url_name='activate_or_deactivate',
            serializer_class=JournalActivateOrDeactivateSerializer)
    def activate_or_deactivate(self, request, pk=None):
        instance = self.get_object()
        serializer = JournalActivateOrDeactivateSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance.is_active = serializer.validated_data.get('is_active')
        instance.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.order_by('-created_date')
    serializer_class = DocumentTypeSerializer
    search_fields = ('name', 'name_uz', 'name_ru')


class DocumentSubTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentSubType.objects.all()
    serializer_class = DocumentSubTypeSerializer
    filterset_fields = ['name', 'document_type']
    search_fields = ['name', ]


class LanguageModelViewSet(viewsets.ModelViewSet):
    queryset = LanguageModel.objects.order_by('-created_date')
    serializer_class = LanguageModelSerializer
    search_fields = ['name', ]


class CountryViewSet(viewsets.ModelViewSet):
    serializer_class = CountrySerializer
    search_fields = ['name', ]
    filterset_class = CountryFilters

    def get_queryset(self):
        queryset = Country.objects.all()
        country_type = self.request.query_params.get('country_type')

        if country_type == 'foreign':
            queryset = queryset.exclude(code='860')

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # check if this country has regions or not
        if instance.regions.count() > 0:
            message = get_response_message(request, 604)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    search_fields = ['name', 'name_uz', 'name_ru']
    filterset_class = RegionFilters

    def get_queryset(self):
        queryset = super().get_queryset()

        region_type = self.request.query_params.get('region_type')  # 'local' or 'foreign'

        if region_type == 'foreign':
            # Exclude Uzbekistan’s regions based on country__name_en
            queryset = queryset.exclude(country__name__iexact="O'zbekiston")
        elif region_type == 'local':
            # Include only Uzbekistan’s regions
            queryset = queryset.filter(country__name__iexact="O'zbekiston")

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # check if this region has districts or not
        if instance.districts.count() > 0:
            message = get_response_message(request, 604)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.order_by('-created_date')
    serializer_class = DistrictSerializer
    filterset_fields = ['region', ]
    search_fields = ['name', 'name_uz', 'name_ru']


class CityDistanceViewSet(viewsets.ModelViewSet):
    queryset = CityDistance.objects.all()
    serializer_class = CityDistanceSerializer
    filterset_fields = ['from_city', 'to_city']
    search_fields = ['from_city__name', 'to_city__name']

    @action(methods=['get'], detail=False, url_path='matrix/(?P<country_id>[^/.]+)', url_name='matrix-view')
    def matrix_view(self, request, country_id=None):
        """
        Provides a distance matrix response for cities within a specified country. The endpoint uses
        the country ID from the request to gather city data and builds a matrix of distances between
        each pair of cities. Distances are fetched from a preloaded lookup table and are symmetric by design.
        If a distance value is unavailable, it will be marked as 'N/A'.

        Parameters:
            request (HttpRequest): The HTTP request object containing request data.

        Returns:
            Response: A Response object containing the distance matrix in an ordered dictionary
                      format with city names as keys, and their respective distances as values.

        """
        country_id = self.kwargs.get('country_id')
        cities = Region.objects.filter(country_id=country_id).order_by('name')

        # Prefetch all distances into a dictionary for fast lookup
        distances = CityDistance.objects.all()
        distance_lookup = {}
        for dist in distances:
            key1 = (dist.from_city_id, dist.to_city_id)
            key2 = (dist.to_city_id, dist.from_city_id)
            distance_lookup[key1] = dist.distance
            distance_lookup[key2] = dist.distance  # make it symmetric if desired

        # Build the matrix
        matrix = OrderedDict()
        for from_city in cities:
            row = OrderedDict()
            for to_city in cities:
                if from_city.id == to_city.id:
                    row[to_city.name] = 0
                else:
                    distance = distance_lookup.get((from_city.id, to_city.id), 'N/A')
                    row[to_city.name] = distance
            matrix[from_city.name] = row

        return Response(matrix, status=status.HTTP_200_OK)


class DeliveryTypeViewSet(viewsets.ModelViewSet):
    queryset = DeliveryType.objects.all()
    serializer_class = DeliveryTypeSerializer
    search_fields = ['name', 'name_uz', 'name_ru']


class PriorityViewSet(viewsets.ModelViewSet):
    queryset = Priority.objects.order_by('-created_date')
    serializer_class = PrioritySerializer
    search_fields = ['name', ]


class ExpenseTypeViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = ExpenseType.objects.order_by('created_date')
    serializer_class = ExpenseTypeSerializer
    search_fields = ['name', ]


class AppVersionViewSet(viewsets.ModelViewSet):
    queryset = AppVersion.objects.all()
    serializer_class = AppVersionSerializer
    search_fields = ['type']
    lookup_field = 'type'
    http_method_names = ['get', 'post', 'put', 'patch']


class AttendanceReasonViewSet(viewsets.ModelViewSet):
    queryset = AttendanceReason.objects.all()
    serializer_class = AttendanceReasonSerializer
    search_fields = ['name', ]


class ExceptionEmployeeViewSet(viewsets.ModelViewSet):
    queryset = ExceptionEmployee.objects.all()
    serializer_class = ExceptionEmployeeSerializer
    search_fields = ['user__first_name', 'user__last_name',]

    def create(self, request, *args, **kwargs):
        user_ids = request.data.get('user_ids', [])
        comment = request.data.get('comment', None)
        created_instances = ExceptionEmployee.objects.process_user_exceptions(user_ids, comment)
        serializer = self.get_serializer(created_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch'], url_path='make-active')
    def make_active(self, request):
        ids = request.data.get('ids', [])
        ExceptionEmployee.objects.make_active(ids)
        return Response({'detail': 'Activated.'})

    @action(detail=False, methods=['patch'], url_path='make-inactive')
    def make_inactive(self, request):
        ids = request.data.get('ids', [])
        comment = request.data.get('comment', None)
        ExceptionEmployee.objects.make_inactive(ids, comment)
        return Response({'detail': 'Deactivated.'})
