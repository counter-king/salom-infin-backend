from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.docflow.filters import ReviewerFilters
from apps.docflow.models import Reviewer
from apps.docflow.serializers import (
    ChangeReviewerSerializer,
    ReviewerDetailSerializer,
    ReviewerSerializer,
)
from apps.docflow.serializers.reviewers import ReviewerPerformSerializer
from apps.reference.models import StatusModel
from apps.reference.tasks import action_log
from config.middlewares.current_user import get_current_user_id
from utils.constant_ids import (
    get_in_progress_base_doc_status_id,
)
from utils.exception import get_response_message
from utils.tools import get_user_ip, get_content_type_id


class ReviewerViewSet(viewsets.ModelViewSet):
    queryset = Reviewer.objects.all()
    serializer_class = ReviewerSerializer
    filterset_class = ReviewerFilters

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewerDetailSerializer
        elif self.action == 'change_reviewer':
            return ChangeReviewerSerializer
        elif self.action == 'perform':
            return ReviewerPerformSerializer
        return ReviewerSerializer

    def get_queryset(self):
        q = super(ReviewerViewSet, self).get_queryset().select_related('document', 'user')
        user_id = get_current_user_id()

        condition = Q(user_id=user_id) | Q(user__assistants__assistant_id=user_id)
        return q.filter(condition).order_by('is_read', '-created_date')

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
        user_id = get_current_user_id()
        if instance.user_id == user_id and instance.read_time:
            message = get_response_message(request, 610)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        assistant_ids = list(instance.user.assistants.values_list('id', flat=True))
        if instance.user_id == user_id or user_id in assistant_ids:
            instance.read_time = timezone.now()
            instance.is_read = True
            instance.status_id = get_in_progress_base_doc_status_id()
            instance.save()

            data = {
                'id': instance.id,
                'is_read': instance.is_read,
                'read_time': str(instance.read_time),
                'user_id': instance.user_id,
                'type': 'review_document_acquainted'
            }

            # a = [instance.user_id]
            # send_to_socket_user(data, *a)

            return Response(data, status=200)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

    def record_activity(self, instance, action, comment=None):
        """
        This function is used to record user's action in the activity log.
        """

        description_code = '137'
        user_id = get_current_user_id()
        user_ip = get_user_ip(self.request)
        ct_id = get_content_type_id(instance.document)
        action_log.apply_async(
            (user_id, 'updated', description_code, ct_id,
             instance.document_id, user_ip, comment, instance.user_id), countdown=2)

    @action(methods=['PUT'], detail=True, url_path='perform', serializer_class=ReviewerPerformSerializer)
    def perform(self, request, *args, **kwargs):
        """
        This function is used to mark a document as performed by the assignee.
        When called, this function handles a PUT request
        to mark a document as performed by the assignee.
        """
        instance = self.get_object()
        user_id = request.user.id
        user_ip = get_user_ip(self.request)
        ct_id = get_content_type_id(instance.document)

        if instance.user_id != user_id:
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        serializer = ReviewerPerformSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        new_content = serializer.validated_data.get('comment')

        if new_content:
            # Get the old content of the document.
            old_content = instance.comment
            self.perform_update(serializer)

            # Get the status of the reviewer.
            reviewer_status = StatusModel.objects.get(is_done=True)

            # Check if the document has been read by the reviewer.
            # If not read, mark the document as read and set the read time.
            # If read, update the status of the reviewer.
            if not instance.is_read:
                serializer.save(status_id=reviewer_status.id, is_read=True, read_time=timezone.now())
            else:
                serializer.save(status_id=reviewer_status.id)

            # Log the action in the activity log.
            if new_content != old_content:
                action_log.apply_async(
                    (user_id, 'updated', '136', ct_id,
                     instance.document_id, user_ip, new_content, old_content), countdown=2)
                return Response(serializer.data, status=status.HTTP_200_OK)

        action_log.apply_async(
            (user_id, 'created', '135', ct_id,
             instance.document_id, user_ip, instance.comment), countdown=2)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True, url_path='change-reviewer', serializer_class=ChangeReviewerSerializer)
    def change_reviewer(self, request, *args, **kwargs):
        """
        Changes the deputy chair (reviewer) for a document.

        When called, this function handles a PUT request to change the deputy chair (reviewer) associated with the document.

        """
        instance = self.get_object()
        user_id = get_current_user_id()
        # Check if the document already has a resolution.
        if instance.has_resolution:
            message = get_response_message(request, 612)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # Check if the current user is the assignee of the document or an assistant to the assignee.
        # is_assistant = user_id in instance.user.assistants if instance.user.assistants else False

        if user_id == instance.user_id:
            serializer = ChangeReviewerSerializer(instance, data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data.get('user')
            doc_id = serializer.validated_data.get('document')
            comment = serializer.validated_data.get('comment', None)

            if Reviewer.objects.filter(user_id=user, document_id=doc_id).exists():
                message = get_response_message(request, 611)
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

            if instance.assignments.exists():
                # If the document already has assignees, return a 400 Bad Request response, indicating that the document
                # cannot be forwarded to another reviewer because they assigned performers.
                message = get_response_message(request, 604)
                return Response(message, status=status.HTTP_400_BAD_REQUEST)
            ref_status = StatusModel.objects.get(is_default=True)
            instance.document_id = doc_id
            instance.user_id = user
            instance.status_id = ref_status.id
            instance.read_time = None
            instance.is_read = False
            instance.save()
            self.record_activity(instance, 'change_reviewer', comment)
            message = get_response_message(request, 800)
            return Response(message)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)
