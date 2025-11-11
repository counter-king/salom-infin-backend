from xmlrpc.client import Fault

import pandas as pd
from io import BytesIO
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import pdfkit
from rest_framework import viewsets, status, mixins, permissions, generics, views
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.compose.filters import (
    BusinessTripFilter,
    TripExpenseFilter,
    TripVerificationFilter,
)
from apps.compose.models import (
    Compose,
    TripVerification,
    TripExpense,
    BusinessTrip,
    TripPlace, VisitedPlace,
)
from apps.compose.serializers import (
    BusinessTripDetailSerializer,
    BusinessTripSerializer,
    TripBaseVerificationSerializer,
    TripExpenseSerializer,
    TripPlaceSerializer,
    VisitedPlaceSerializer,
    RestoreTripVerificationSerializer,
)
from apps.compose.serializers.v1.compose import UpdateTripVerificationSerializer
from apps.compose.tasks.utils import (
    add_object_id_to_trip,
)
from apps.compose.views.v1.trips.statistics import trips_by_status, trips_by_top_departments, trips_line_graph_by_type, \
    trips_by_locations, trips_by_route, trips_by_goals, trip_expense_line_graph
from apps.reference.models import Region
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2


class BusinessTripViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin):
    queryset = BusinessTrip.objects.prefetch_related('destinations').order_by('-created_date')
    serializer_class = BusinessTripSerializer
    filterset_class = BusinessTripFilter
    search_fields = ('user__first_name', 'user__last_name', 'user__father_name', 'user__table_number')

    # permission_classes = [DynamicPermission]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BusinessTripDetailSerializer
        return BusinessTripSerializer

    def get_queryset(self):
        user = self.request.user
        has_hr_role = user.roles.filter(name='hr').exists()
        queryset = BusinessTrip.objects.select_related(
            'notice', 'order', 'user', 'company'
        ).prefetch_related(
            'destinations', 'locations', 'tags'
        ).filter(
            ~Q(trip_type__in=[
                CONSTANTS.COMPOSE.TRIP_TYPE.CHANGED_LOCAL,
                CONSTANTS.COMPOSE.TRIP_TYPE.CHANGED_FOREIGN,
                CONSTANTS.COMPOSE.TRIP_TYPE.FOREIGN,
            ])
        )

        if not has_hr_role:
            if self.action == 'retrieve':
                queryset = queryset.filter(
                    Q(user_id=user.id) | Q(notice__author_id=user.id)
                )
            else:
                queryset = queryset.filter(user_id=user.id)


        return (queryset.
                filter(Q(order__is_signed=True) |
                       (Q(notice__document_sub_type_id__in=[29]) &
                        Q(notice__is_signed=True))).
                order_by('-created_date'))

    group_id = openapi.Parameter('group_id', openapi.IN_QUERY,
                                 description="Group ID",
                                 type=openapi.TYPE_INTEGER)

    response = openapi.Response('response description', BusinessTripSerializer)

    @swagger_auto_schema(manual_parameters=[group_id], responses={200: response})
    @action(methods=['get'], detail=True, url_name='next-destinations', url_path='next-destinations')
    def next_destinations(self, request, pk=None):
        """
        This method retrieves the next destinations information for a specific trip. It filters
        the trip verifications related to a trip and group, identifying regions that have not
        been arrived at yet. The method ensures the returned destinations are unique and
        provides details like ID, name, and type for each.

        Args:
            request: The HTTP request object containing metadata about the request.
            pk: Optional; The primary key of the instance for which the destinations are
                retrieved.

        Returns:
            Response: Returns an HTTP 200 response containing a list of next destinations.
                Each destination includes 'id', 'name', and 'type'.

        Raises:
            Not specified, error handling depends on the get_object() and other invoked methods.
        """
        instance = self.get_object()
        group_id = self.request.GET.get('group_id')
        trip_verifications = (TripVerification.objects.
                              select_related('trip').
                              filter(trip_id=instance.id,
                                     trip__group_id=group_id))
        next_destinations = []
        seen = set()

        for tp in trip_verifications:
            if not tp.arrived_at:
                if tp.region_id in seen:
                    continue
                next_destinations.append({
                    "id": tp.region_id,
                    "name": tp.region.name if tp.region else None,
                    "type": "region"
                })
                seen.add(tp.region_id)

        return Response(next_destinations, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='export-excel')
    def export_excel(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        data = []
        for idx, trip in enumerate(queryset, start=1):
            location_names = ', '.join([loc.name for loc in trip.locations.all()]) if trip.locations.exists() else ''
            data.append({
                'No': idx,
                'F.I.Sh.': f"{trip.user.first_name} {trip.user.last_name}" if trip.user else '',
                'Tabel raqami': trip.user.iabs_emp_id if trip.user else '',
                'Tarkibiy bo‘linma': trip.user.top_level_department.name if trip.user and trip.user.top_level_department else '',
                'Qayerdan': trip.sender_company.name if trip.sender_company else '',
                'Qayerga': location_names,
                'Boshlanish sanasi': trip.start_date.strftime('%d.%m.%Y') if trip.start_date else '',
                'Tugash sanasi': trip.end_date.strftime('%d.%m.%Y') if trip.end_date else '',
                'Holati': dict(BusinessTrip.STATUS_CHOICES).get(trip.trip_status, ''),
            })

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Xizmat safarlari')
            workbook = writer.book
            worksheet = writer.sheets['Xizmat safarlari']

            # Define header format with light blue background
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'center',
                'fg_color': '#D9E1F2',  # Light blue
                'border': 1
            })

            # Apply the header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Autofit column width based on data
            for i, col in enumerate(df.columns):
                column_len = max(
                    df[col].astype(str).map(len).max(),  # max length of column content
                    len(col)  # length of column header
                ) + 2
                worksheet.set_column(i, i, column_len)

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="business_trips.xlsx"'
        response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response


class SetPlaceToTripViewSet(viewsets.GenericViewSet,
                            mixins.CreateModelMixin):
    queryset = VisitedPlace.objects.all()
    serializer_class = VisitedPlaceSerializer


class TripVerificationViewSet(viewsets.GenericViewSet,
                              mixins.ListModelMixin,
                              mixins.RetrieveModelMixin,
                              mixins.UpdateModelMixin):
    queryset = TripVerification.objects.all().order_by('created_date')
    serializer_class = TripBaseVerificationSerializer
    filterset_class = TripVerificationFilter

    def all_verified(self, instance):
        """
        This function is responsible for checking if all trips have been verified.
        """

        return not TripVerification.objects.filter(trip_id=instance.trip_id, verified=False).exists()

    @action(methods=['put'], detail=True, url_name='arrived', url_path='mark-arrived')
    def arrived(self, request, *args, **kwargs):
        """
        Marks a trip as arrived with validation checks and updates the trip's state accordingly.

        This function handles the process of marking a trip as arrived, ensuring that it adheres to various
        business rules like validating if previous trips are completed and verifying that the employee is
        authorized to mark the trip as arrived. If any validation fails, an error is raised. On success,
        the trip's arrival details are updated and saved.

        Parameters:
        request : Request
            The HTTP request object containing the user and request data like address, latitude, and longitude.
        *args : tuple
            Positional arguments passed to the method.
        **kwargs : dict
            Keyword arguments passed to the method.

        Raises:
        ValidationError2
            If any validation rule is violated, a ValidationError2 exception is raised with the appropriate message.

        Returns:
        Response
            A response containing a confirmation message and the timestamp of when the employee arrived, with
            an HTTP 200 status code.
        """
        instance = self.get_object()

        if not instance.trip.is_active:
            message = get_response_message(request, 655)
            raise ValidationError2(message)

        user = request.user
        address = request.data.get('address', None)
        lat = request.data.get('lat', None)
        lng = request.data.get('lng', None)

        trips = TripVerification.objects.filter(trip_id=instance.trip_id)

        # if the last trip has not been left
        # then the current trip cannot be marked as arrived
        last_trip = trips.filter(action_date__isnull=False).order_by('-action_date').first()
        if last_trip and last_trip.left_at is None:
            message = get_response_message(request, 635)
            raise ValidationError2(message)

        # if the employee has not left the initial address
        # then the user cannot mark as arrived
        sender = trips.filter(is_sender=True).first()
        if sender and sender.left_at is None:
            message = get_response_message(request, 636)
            raise ValidationError2(message)

        # if the employee works for the same company as the user who created the trip
        # and all addresses have been visited
        # then the user can verify the trip
        # otherwise the user cannot verify the trip
        if instance.trip.user.company_id == user.company_id:
            if not self.all_verified(instance):
                message = get_response_message(request, 634)
                raise ValidationError2(message)

        # if the employee has already arrived
        # then the employee cannot mark as arrived again
        if instance.arrived_at is not None:
            message = get_response_message(request, 632)
            raise ValidationError2(message)

        # if the employee visits A company and the user works for B company
        # then the user cannot verify the trip
        # if user.company_id != instance.company_id:
        #     message = get_response_message(request, 700)
        #     raise ValidationError2(message)

        instance.arrived_at = timezone.now()
        instance.action_date = timezone.now()
        instance.arrived_verified_by_id = user.id
        instance.arrived_lat = lat
        instance.arrived_lng = lng
        instance.arrived_address = address
        instance.save()

        if instance.is_sender:
            instance.trip.trip_status = 'reporting'
            instance.trip.save()

        return Response({'message': 'ok', 'arrived_at': instance.arrived_at},
                        status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True, url_name='left', url_path='mark-left')
    def left(self, request, *args, **kwargs):
        """
        Handles the process of marking a specific object as 'left' with associated metadata updates.

        This action updates the relevant fields of an instance when the user marks that the instance has
        left its current position. It also validates whether the operation is allowed based on the
        instance's state and user's input data before performing the updates. Additionally, related
        data, such as trip status, is modified if applicable.

        Args:
            request (Request): The HTTP request containing user and payload data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Raises:
            ValidationError2:
                Raised when the object cannot be marked as left due to specific state conditions, such
                as not being arrived yet, already marked as left, or validation issues with the request data.

        Returns:
            Response: A Response object containing a message and the timestamp when the object was
            marked as left, with a status of HTTP 200 OK.
        """
        instance = self.get_object()

        if not instance.trip.is_active:
            message = get_response_message(request, 655)
            raise ValidationError2(message)

        user = request.user
        next_destination_type = request.data.get('next_destination_type', None)
        next_destination_id = request.data.get('next_destination_id', None)
        address = request.data.get('address', None)
        lat = request.data.get('lat', None)
        lng = request.data.get('lng', None)

        if instance.arrived_at is None and instance.is_sender is False:
            message = get_response_message(request, 631)
            raise ValidationError2(message)

        # if user.company_id != instance.company_id:
        #     message = get_response_message(request, 700)
        #     raise ValidationError2(message)

        if instance.left_at is not None:
            message = get_response_message(request, 633)
            raise ValidationError2(message)

        instance.left_at = timezone.now()
        instance.action_date = timezone.now()
        instance.left_verified_by_id = user.id
        instance.verified = True
        instance.next_destination_type = next_destination_type
        instance.next_destination_id = next_destination_id
        instance.left_lat = lat
        instance.left_lng = lng
        instance.left_address = address
        instance.save()

        if next_destination_id:
            # 🔹 Check existing verification for this region
            existing_verification = TripVerification.objects.filter(
                trip_id=instance.trip_id,
                region_id=next_destination_id
            ).order_by("-created_date").first()

            # 🔹 If no existing verification → do nothing
            if existing_verification:
                # Only create if the last one was completed
                if existing_verification.arrived_at and existing_verification.left_at:
                    TripVerification.objects.create(
                        trip=instance.trip,
                        region_id=next_destination_id,
                        is_sender=False,
                        company_id=None
                    )

        if instance.is_sender:
            instance.trip.trip_status = 'on_trip'
            instance.trip.save()

        return Response({'message': 'ok', 'left_at': instance.left_at},
                        status=status.HTTP_200_OK)


class TripPlaceViewSet(viewsets.GenericViewSet,
                       mixins.ListModelMixin,
                       mixins.CreateModelMixin):
    queryset = TripPlace.objects.all().order_by('created_date')
    serializer_class = TripPlaceSerializer
    search_fields = ('name', 'address')


class TripExpenseViewSet(viewsets.GenericViewSet,
                         mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.DestroyModelMixin):
    queryset = TripExpense.objects.order_by('created_date')
    serializer_class = TripExpenseSerializer
    filterset_class = TripExpenseFilter

    # def get_queryset(self):
    #     trip_id = self.request.query_params.get('trip')
    #
    #     if not trip_id:
    #         message = get_response_message(self.request, 600)
    #         message['message'] = message['message'].format(type='trip')
    #         raise ValidationError2(message)
    #
    #     return super().get_queryset().filter(trip_id=trip_id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request},
                                         many=isinstance(request.data, list))
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RestoreTripVerification(generics.GenericAPIView):
    serializer_class = RestoreTripVerificationSerializer
    permission_classes = [permissions.IsAdminUser, ]

    def post(self, request, *args, **kwargs):
        """
        Handles the HTTP POST request and performs asynchronous task dispatch.

        Checks the validity of incoming request data using a serializer. Retrieves the
        validated data, processes it, and triggers an asynchronous task to associate
        a decree object with a trip. The operation is carried out based on the provided
        data.

        Parameters:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Raises:
            ValidationError: Raised if the serializer data is invalid.
            Http404: Raised if the specified decree object is not found.

        Returns:
            Response: A Response object with a success message and HTTP status code 200.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decree_id = serializer.validated_data.get('decree_id')
        create_trip = serializer.validated_data.get('create_trip')
        compose = get_object_or_404(Compose, id=decree_id)
        add_object_id_to_trip.apply_async((compose.trip_notice_id, decree_id), {
            'create_trip': create_trip,
        })

        return Response({'message': 'ok'}, status=status.HTTP_200_OK)


class TripsByStatusView(views.APIView):
    """View for retrieving trips based on their status within a specific date range.

    This view filters and retrieves trips by their status and a given date range,
    as provided through query parameters in the HTTP request.
    The response includes details for each trip such as its ID, user ID, and status.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve and group trips by their status within a
        specified date range. The request requires query parameters defining the
        start and end dates. The response contains the grouped trips data and a status
        code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the grouped trips data and status code 200.

        Raises:
            KeyError
                If required query parameters 'start_date' or 'end_date' are missing.
            ValueError
                If the supplied dates are in an invalid format.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Group trips by status within the specified date range
        result = trips_by_status(start_date, end_date)

        return Response(result, status=200)


class TripsByDepartmentView(views.APIView):
    """View for retrieving trips by department within a specific date range.

    This view filters and retrieves trips based on their department and a given date range,
    as provided through query parameters in the HTTP request.
    The response includes details for each trip such as its ID, user ID, and department.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trips by department within a specified date range.
        The request requires query parameters defining the start and end dates. The response
        contains the grouped trips data by department and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the grouped trips data by department and status code 200.

        Raises:
            KeyError
                If required query parameters 'start_date' or 'end_date' are missing.
            ValueError
                If the supplied dates are in an invalid format.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Group trips by department within the specified date range
        result = trips_by_top_departments(start_date, end_date)

        return Response(result, status=200)


class TripsByTypeLineGraphView(views.APIView):
    """View for retrieving trips by type in a line graph format.

    This view retrieves trips grouped by type and formatted for a line graph representation.
    The response includes the trip types and their respective counts.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=True)

    @swagger_auto_schema(manual_parameters=[start_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trips by type for a line graph.
        The request requires a query parameter defining the start date. The response
        contains the trips data formatted for a line graph and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the trips data formatted for a line graph and status code 200.
        """
        start_date = request.GET.get('start_date')

        # Retrieve trips by type for line graph representation
        result = trips_line_graph_by_type(start_date)

        return Response(result, status=200)


class TripsByLocationsView(views.APIView):
    """View for retrieving trips by their locations.

    This view retrieves the count of business trips grouped by their locations.
    The response includes the location names and the respective counts of trips.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=False)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=False)
    type = openapi.Parameter('type', openapi.IN_QUERY,
                             description="local or foreign",
                             type=openapi.TYPE_STRING, required=False)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trips by their locations.
        The request can include optional query parameters defining the start and end dates.
        The response contains the count of trips by location and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the count of trips by location and status code 200.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        location_type = request.GET.get('type', 'local')

        # Retrieve trips by locations
        result = trips_by_locations(start_date, end_date, location_type)

        return Response(result, status=200)


class TripsByRouteView(views.APIView):
    """View for retrieving trips by their route.

    This view retrieves the count of business trips grouped by their route.
    The response includes the route names and the respective counts of trips.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=False)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=False)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trips by their route.
        The request can include optional query parameters defining the start and end dates.
        The response contains the count of trips by route and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the count of trips by route and status code 200.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Retrieve trips by route
        result = trips_by_route(start_date, end_date)

        return Response(result, status=200)


class TripsByTagView(views.APIView):
    """View for retrieving trips by their tags.

    This view retrieves the count of business trips grouped by their tags.
    The response includes the tag names and the respective counts of trips.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=False)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=False)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trips by their tags.
        The request can include optional query parameters defining the start and end dates.
        The response contains the count of trips by tag and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the count of trips by tag and status code 200.
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Retrieve trips by tags
        result = trips_by_goals(start_date, end_date)

        return Response(result, status=200)


class TripExpenseGraphView(views.APIView):
    """View for retrieving trip expenses in a graph format.

    This view retrieves trip expenses grouped by their type and formatted for a graph representation.
    The response includes the expense types and their respective counts.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=True)

    @swagger_auto_schema(manual_parameters=[start_date], responses={200: 'Success'})
    def get(self, request, *args, **kwargs):
        """
        Handles HTTP GET requests to retrieve trip expenses for a graph.
        The request requires a query parameter defining the start date. The response
        contains the trip expenses data formatted for a graph and a status code.

        Parameters:
            request: HttpRequest
                The HTTP request object containing details of the GET request.
            *args
                Additional positional arguments.
            **kwargs
                Additional keyword arguments.

        Returns:
            Response
                An HTTP response containing the trip expenses data formatted for a graph and status code 200.
        """
        start_date = request.GET.get('start_date')

        # Retrieve trip expenses for graph representation
        result = trip_expense_line_graph(start_date)

        return Response(result, status=200)


class UpdateTripVerificationsAPIView(generics.GenericAPIView):
    serializer_class = UpdateTripVerificationSerializer

    def post(self, request, business_trip_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        region_ids = serializer.data.get('region_ids', [])
        end_date = serializer.data.get('end_date')

        if not isinstance(region_ids, list) or not end_date:
            return Response({"message": "Missing or invalid 'regions' or 'end_date'."},
                            status=status.HTTP_400_BAD_REQUEST)

        trip = get_object_or_404(BusinessTrip, id=business_trip_id)

        # Update BusinessTrip
        trip.end_date = end_date
        trip.is_active = False
        trip.save()

        # Get existing verifications
        existing_verifications = TripVerification.objects.filter(trip=trip).select_related(
            'region'
        )
        existing_region_ids = set()
        to_delete_ids = []

        for v in existing_verifications:
            if v.is_sender:
                continue
            if v.region and v.region.id in region_ids:
                existing_region_ids.add(v.region.id)
            elif not v.arrived_at and not v.left_at:
                to_delete_ids.append(v.id)

        if to_delete_ids:
            TripVerification.objects.filter(id__in=to_delete_ids).delete()

        # Fetch all regions in a single query
        regions = Region.objects.in_bulk(region_ids)
        if len(regions) != len(region_ids):
            missing_ids = set(region_ids) - set(regions.keys())
            return Response({"message": f"Regions not found: {missing_ids}"})

        new_verifications = []
        for region_id in region_ids:
            if region_id not in existing_region_ids:
                new_verifications.append(
                    TripVerification(trip=trip, region=regions[region_id])
                )

        if new_verifications:
            TripVerification.objects.bulk_create(new_verifications)

        return Response(
            {"message": "Trip verifications and business trip updated successfully."},
            status=status.HTTP_200_OK
        )


class ResetTripVerificationAPIView(views.APIView):
    """
    View for resetting trip verification fields.
    """

    ALLOWED_TYPES = ('left', 'arrived')

    def _raise_error(self, request, code, object=None, status_code=status.HTTP_400_BAD_REQUEST):
        """
        Helper method to raise ValidationError2
        with formatted message
        """
        error_message = get_response_message(request, code)
        if object is not None:
            error_message['message'] = error_message['message'].format(object=object)
        raise ValidationError2(error_message, status_code=status_code)

    def post(self, request, pk):
        t = request.data.get('type')

        if t not in self.ALLOWED_TYPES:
            self._raise_error(request, 659, object=t)

        tv = get_object_or_404(TripVerification, pk=pk)

        # 1. If resetting sender-left, ensure no non-sender has already been to another region
        if tv.is_sender and t == 'left':
            other_exists = TripVerification.objects.filter(
                trip=tv.trip,
                is_sender=False
            ).filter(
                Q(arrived_at__isnull=False) | Q(left_at__isnull=False)
            ).exists()
            if other_exists:
                self._raise_error(request, 659)

        # 2. If resetting a non-sender left without ever having arrived
        if not tv.is_sender and t == 'left' and tv.arrived_at is None:
            self._raise_error(request, 660)

        # 3. If trying to reset arrived but this record has already been left
        if t == 'arrived' and tv.left_at is not None and tv.is_sender is False:
            self._raise_error(request, 661)

        # 4 if resetting verification is sender make trip status to 'on_trip'
        if t == 'arrived' and tv.is_sender is True:
            tv.trip.trip_status = 'on_trip'
            tv.trip.save()

        if t == 'left':
            fields_to_reset = [
                'left_at',
                'left_verified_by',
                'next_destination_type',
                'next_destination_id',
                'left_lat',
                'left_lng',
                'left_address',
                'verified'
            ]
        else:  # t == 'arrived'
            VisitedPlace.objects.filter(trip_verification=tv).delete()
            fields_to_reset = [
                'arrived_at',
                'arrived_verified_by',
                'action_date',
                'arrived_lat',
                'arrived_lng',
                'arrived_address'
            ]

        for field in fields_to_reset:
            setattr(tv, field, None)

        tv.save()
        return Response(
            {"message": f"{t} fields reset successfully."},
            status=status.HTTP_200_OK
        )


class VisitedPlaceViewSet(mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    """
    DELETE /api/v1/visited-places/{pk}/
    """
    queryset = VisitedPlace.objects.all()
    serializer_class = VisitedPlaceSerializer


class BusinessTripCertificateToPdfView(views.APIView):
    def post(self, request, *args, **kwargs):
        context = request.data
        html_content = render_to_string('letters/trip_certificate.html', context)

        options = {
            'page-size': 'A4',
            'encoding': 'UTF-8',
            'margin-top': '16mm',
            'margin-bottom': '16mm',
            'margin-left': '16mm',
            'margin-right': '16mm',
            'zoom': '1.3',
        }

        pdf = pdfkit.from_string(html_content, False, options=options)

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="business_trip_certificate.pdf"'
        return response
