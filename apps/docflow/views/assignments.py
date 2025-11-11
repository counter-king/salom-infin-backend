from typing import Dict, Tuple

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.docflow.filters import AssigneeFilters, AssignmentFilters
from apps.docflow.models import Reviewer, Assignment, Assignee
from apps.docflow.serializers import (
    AssignmentSerializer,
    MyAssignmentSerializer,
    MyResolutionDetailSerializer,
    MyResolutionSerializer,
    PerformSerializer,
    PerformerSerializer,
    VerifyOrRejectResolutionSerializer,
)
from apps.reference.models import StatusModel
from apps.reference.tasks import action_log
from config.middlewares.current_user import get_current_user_id
from utils.constant_ids import (
    get_completed_base_doc_status_id,
    get_in_progress_base_doc_status_id,
    get_on_hold_base_doc_status_id,
)
from utils.exception import get_response_message
from utils.tools import get_user_ip, get_content_type_id


class ResolutionViewSet(viewsets.GenericViewSet,
                        mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin,
                        mixins.DestroyModelMixin):
    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer

    @action(methods=['GET'], detail=True, serializer_class=PerformerSerializer)
    def performers(self, request, *args, **kwargs):
        instance = self.get_object()
        performers = instance.assignees.all()
        performers_serializer = PerformerSerializer(performers, many=True)
        return Response({'performers': performers_serializer.data})

    def record_activity(self, instance, action: str, comment=None) -> None:
        """
        This function is used to record user's action in the activity log.
        """
        user_id = get_current_user_id()
        user_ip = get_user_ip(self.request)
        document_instance = instance.reference.document
        ct_id = get_content_type_id(document_instance)

        # Map incoming UI action -> (description_code, event_action stored in ActionModel.action)
        ACTION_MAP: Dict[str, Tuple[str, str]] = {
            "cancel_assignment": ("134", "updated"),
            "verify_assignment": ("138", "updated"),
            "delete_assignment": ("133", "deleted"),
        }
        mapped = ACTION_MAP.get(action)

        # If action not found, fail silently
        if not mapped:
            return

        description_code, action_type = mapped

        action_log.apply_async(
            (user_id, action_type, description_code,
             ct_id, document_instance.id, user_ip, comment), countdown=2)

    @action(methods=['PUT'], detail=False, url_path='verify-or-cancel',
            serializer_class=VerifyOrRejectResolutionSerializer)
    def verify(self, request, *args, **kwargs):
        """
        after adding assignees by reviewers or their assistants,
        assignment should be verified by reviewers (chair or deputy chair)
        """

        current_user_id = get_current_user_id()
        assistants = []
        # is_user_assistant = current_user_id in assistants if assistants else False

        serializer = VerifyOrRejectResolutionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        is_verified = serializer.validated_data.get('is_verified')
        comment = serializer.validated_data.get('comment', None)
        pkcs7 = serializer.validated_data.get('pkcs7', None)
        assignment_ids = serializer.validated_data.get('assignment_ids', None)

        assignment = Assignment.objects.filter(id__in=assignment_ids)

        for instance in assignment:
            review = instance.reviewer
            if review.user_id != current_user_id:
                message = get_response_message(request, 700)
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if is_verified:
            assignment.update(is_verified=True, receipt_date=timezone.now())
            for assignment_instance in assignment:
                self.record_activity(assignment_instance, 'verify_assignment', comment)
            return Response({'is_verified': True}, status=status.HTTP_200_OK)
        else:
            assignment.update(is_verified=False)
            for assignment_instance in assignment:
                self.record_activity(assignment_instance, 'cancel_assignment', comment)
            message = get_response_message(request, 802)
            return Response(message, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Endpoint for deleting a document assignment.

        This endpoint allows authorized users to delete a document assignment. The user must have the necessary
        permissions to perform this action, and the assignment must meet certain conditions for deletion.

        Returns:
            Response: A JSON response indicating the status of the deletion operation.
                      If successful, returns status code 204 (HTTP_204_NO_CONTENT).
                      If the user does not have the necessary permissions, returns status code 400 (HTTP_400_BAD_REQUEST).
                      If the document instance does not exist, returns status code 404 (HTTP_404_NOT_FOUND).
        """

        instance = self.get_object()

        # Get the deletion comment from query parameters.
        comment = request.query_params.get('comment', '1')
        user_id = request.user.id

        # Check if the assignment is a verified project resolution, which cannot be deleted.
        if instance.is_verified and instance.is_project_resolution:
            message = get_response_message(request, 616)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if not comment and instance.is_project_resolution:
            message = get_response_message(request, 617)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # Check if the user is an assistant of the review's user.
        # is_user_assistant = user_id in instance.reviewer.user.assistants if instance.reviewer.user.assistants else False
        if instance.is_project_resolution and (instance.reviewer.user_id == user_id):
            instance.reviewer.has_resolution = False
            instance.reviewer.status_id = StatusModel.objects.get(is_default=True).id
            instance.reviewer.save()
            self.record_activity(instance, 'delete_assignment', comment)
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

        if instance.created_by_id == user_id:
            self.perform_destroy(instance)
            self.record_activity(instance, 'delete_assignment', comment)
            return Response(status=status.HTTP_204_NO_CONTENT)

        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)


class MyResolutionViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Assignment.objects.all()
    serializer_class = MyResolutionSerializer
    filterset_class = AssignmentFilters

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MyResolutionDetailSerializer
        return MyResolutionSerializer

    def get_queryset(self):
        q = super(MyResolutionViewSet, self).get_queryset().select_related('reviewer', 'reviewer__document')
        current_user_id = get_current_user_id()
        search = self.request.query_params.get('search', None)

        condition = Q(created_by_id=current_user_id)
        q = q.filter(condition)

        if search:
            q = q.filter(Q(reviewer__document__register_number__icontains=search) |
                         Q(reviewer__document__description__icontains=search))

        return q.distinct().order_by('-created_date')


class MyAssignmentViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin):
    queryset = Assignee.objects.all()
    serializer_class = MyAssignmentSerializer
    filterset_class = AssigneeFilters

    def get_queryset(self):
        q = ((super(MyAssignmentViewSet, self).get_queryset().
        select_related(
            'assignment', 'user',
            'assignment__reviewer', 'status', )).
             prefetch_related('files'))
        current_user_id = self.request.user.id
        search = self.request.query_params.get('search', None)

        condition = Q(user_id=current_user_id)
        is_verified = Q(assignment__is_verified=True)
        is_controller = Q(is_controller=False)
        q = q.filter(condition & is_controller & is_verified)

        if search:
            q = q.filter(Q(assignment__reviewer__document__register_number__icontains=search) |
                         Q(assignment__reviewer__document__description__icontains=search))

        return q.distinct().order_by('is_read', '-created_date')

    @action(methods=['put'], detail=True)
    def acquaint(self, request, *args, **kwargs):
        """
        This custom action is used in a Django Rest Framework view set to handle a PUT request,
        marking a document as read by the assignee or an assistant in a review user.

        Returns:
        - 200 OK response if the document is successfully marked as read.
        - 400 Bad Request response if the document has already been read by the user.
        - 404 Not Found.
        - 200 OK response with a message if the user is not authorized to perform this action.
        """
        instance = self.get_object()
        user_id = self.request.user.id
        if instance.user_id == user_id and instance.read_time:
            message = get_response_message(request, 610)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if instance.user_id == user_id:
            instance.read_time = timezone.now()
            instance.is_read = True
            instance.status_id = get_in_progress_base_doc_status_id()
            instance.save()

            data = {
                'id': instance.id,
                'read_time': str(instance.read_time),
                'user_id': instance.user_id,
                'type': 'performer_acquainted'
            }

            # a = [instance.user_id]
            # send_to_socket_user(data, *a)

            return Response(data, status=200)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

    def update_parent_status(self, model, obj_id: int, status_id: int) -> None:
        """
        This function updates the status of the parent assignment
        when the assignee marks the document as performed.
        """
        done_status_id = get_completed_base_doc_status_id()
        model.objects.filter(id=obj_id).exclude(status_id=done_status_id).update(status_id=status_id)

    @action(methods=['PUT'], detail=True, url_path='perform', serializer_class=PerformSerializer)
    def perform(self, request, *args, **kwargs):
        """
        This function is used to mark a document as performed by the assignee.
        When called, this function handles a PUT request to mark a document as performed by the assignee.
        """
        instance = self.get_object()
        user_id = request.user.id
        user_ip = get_user_ip(self.request)
        document = instance.assignment.reviewer.document
        ct_id = get_content_type_id(document)
        object_id = document.id

        if instance.user_id != user_id:
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # Check if the document has been read by the assignee.
        # If the document has not been read, return a 400 Bad Request response.
        if not instance.is_read:
            message = get_response_message(request, 618)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        serializer = PerformSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        if instance.is_performed:
            new_content = serializer.validated_data.get('content')
            old_content = instance.content
            self.perform_update(serializer)

            if new_content != old_content:
                action_log.apply_async(
                    (user_id, 'updated', '136', ct_id,
                     object_id, user_ip, new_content, old_content), countdown=2)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer.save(is_performed=True, performed_date=timezone.now(), status_id=get_completed_base_doc_status_id())
        # Log the action in the activity log.
        action_log.apply_async(
            (user_id, 'created', '135', ct_id,
             object_id, user_ip, instance.content), countdown=2)

        # Update the status of the parent assignment.
        on_hold_id = get_on_hold_base_doc_status_id()
        if instance.parent:
            # If the assignment has a parent, update the status of the parent assignment
            self.update_parent_status(Assignee, instance.parent.id, on_hold_id)
        else:
            # If the assignment does not have a parent, update the status of the reviewer
            self.update_parent_status(Reviewer, instance.assignment.reviewer.id, on_hold_id)

        return Response(serializer.data, status=status.HTTP_200_OK)


class MyControlViewSet(viewsets.GenericViewSet,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin):
    queryset = Assignee.objects.all()
    serializer_class = MyAssignmentSerializer
    filterset_class = AssigneeFilters

    def get_queryset(self):
        q = ((super(MyControlViewSet, self).get_queryset().
              select_related('assignment', 'user',
                             'assignment__reviewer', 'status')).
             prefetch_related('files'))
        current_user_id = self.request.user.id
        search = self.request.query_params.get('search', None)

        condition = Q(user_id=current_user_id)
        is_verified = Q(assignment__is_verified=True)
        is_controller = Q(is_controller=True)
        q = q.filter(condition & is_controller & is_verified)

        if search:
            q = q.filter(Q(assignment__reviewer__document__register_number__icontains=search) |
                         Q(assignment__reviewer__document__description__icontains=search))

        return q.distinct().order_by('is_read', '-created_date')

    @action(methods=['put'], detail=True)
    def acquaint(self, request, *args, **kwargs):
        """
        This custom action is used in a Django Rest Framework viewset to handle a PUT request,
        marking a document as read by the assignee or an assistant in a review user.

        Returns:
        - 200 OK response if the document is successfully marked as read.
        - 400 Bad Request response if the document has already been read by the user.
        - 404 Not Found.
        - 200 OK response with a message if the user is not authorized to perform this action.
        """
        instance = self.get_object()
        user_id = self.request.user.id
        if instance.user_id == user_id and instance.read_time:
            message = get_response_message(request, 610)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if instance.user_id == user_id:
            instance.read_time = timezone.now()
            instance.is_read = True
            instance.save()

            data = {
                'id': instance.id,
                'read_time': str(instance.read_time),
                'user_id': instance.user_id,
                'type': 'performer_acquainted'
            }

            # a = [instance.user_id]
            # send_to_socket_user(data, *a)

            return Response(data, status=200)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

    def set_other_status_as_completed(self, assignment_id, status_id):
        """
        This function sets other assignees' status as COMPLETED
        when assignment type is control point
        that's why they do not have to complete task after removed from control
        """

        (Assignee.objects.
         filter(assignment_id=assignment_id, is_controller=False).
         update(is_performed=True, status_id=status_id))

    @action(methods=['PUT'], detail=True,
            url_path='remove-from-control',
            serializer_class=PerformSerializer)
    def remove_from_control(self, request, *args, **kwargs):
        """
        This function is used to mark a document as performed by the assignee.
        When called, this function handles a PUT request to mark a document as performed by the assignee.
        """
        instance = self.get_object()
        user_id = request.user.id
        user_ip = get_user_ip(self.request)
        document = instance.assignment.reviewer.document
        ct_id = get_content_type_id(document)
        object_id = document.id

        if instance.user_id != user_id:
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if not instance.is_read:
            message = get_response_message(request, 618)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        serializer = PerformSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        if instance.is_performed:
            new_content = serializer.validated_data.get('content')
            old_content = instance.content
            self.perform_update(serializer)
            if new_content != old_content:
                action_log.apply_async(
                    (user_id, 'updated', '139', ct_id, object_id,
                     user_ip, new_content, old_content), countdown=2)
            return Response(serializer.data, status=status.HTTP_200_OK)

        status_id = StatusModel.objects.get(is_done=True).id
        serializer.save(is_performed=True, performed_date=timezone.now(), status_id=status_id)
        action_log.apply_async(
            (user_id, 'created', '130', ct_id,
             object_id, user_ip, instance.content), countdown=2)
        self.set_other_status_as_completed(instance.assignment.id, status_id)

        return Response(serializer.data, status=status.HTTP_200_OK)
