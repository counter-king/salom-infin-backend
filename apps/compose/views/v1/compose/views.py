import os
import time

from django.db.models import Q, F
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from rest_framework import viewsets, status, mixins, permissions, views
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.compose.filters import (
    ApproverFilter,
    ComposeFilter,
    SignerFilter,
    TagFilter, IABSActionHistoryFilter,
)
from apps.compose.models import (
    Approver,
    Compose,
    ComposeStatus,
    ComposeVersionModel,
    Signer,
    Tag,
    ComposeLink,
    IABSActionHistory, IABSRequestCallHistory, BusinessTrip,
)
from apps.compose.serializers import (
    ApproveDetailSerializer,
    ApproveListSerializer,
    ApproveSerializer,
    ComposeCustomUpdateSerializer,
    ComposeLinkSerializer,
    ComposeListSerializer,
    ComposeSerializer,
    ComposeStatusSerializer,
    ComposeVersionSerializer,
    SignerListSerializer,
    TagSerializer,
    ComposeVerifySerializer,
    SignerList2Serializer,
    SignerDetailSerializer,
    IABSActionHistorySerializer,
)
from apps.compose.serializers.v1.compose import IABSRequestCallHistorySerializer
from apps.compose.serializers.v1.compose.iabs_actions import IABSRetryActionSerializer
from apps.compose.services import DigitalSignatureService, IABSRequestService
from apps.compose.tasks.delays import create_compose_version
from apps.compose.tools import register_document_after_signing
from apps.docflow.models import BaseDocument
from apps.document.models import MINIO_CLIENT, MINIO_BUCKET_NAME
from apps.reference.models import DigitalSignInfo
from apps.reference.tasks import action_log
from config.middlewares.current_user import get_current_user_id
from utils.constant_ids import get_compose_status_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.tools import (
    clean_html,
    remove_all_whitespaces,
    get_user_ip,
    get_content_type_id,
)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('-created_date')
    serializer_class = TagSerializer
    filterset_class = TagFilter
    search_fields = ('name',)


class ComposeListViewSet(viewsets.GenericViewSet,
                         mixins.ListModelMixin):
    queryset = Compose.objects.order_by('-created_date').distinct()
    serializer_class = ComposeSerializer
    filterset_class = ComposeFilter
    search_fields = ('title', 'register_number')


class ComposeViewSet(viewsets.ModelViewSet):
    queryset = Compose.objects.all()
    serializer_class = ComposeSerializer
    filterset_class = ComposeFilter

    # permission_classes = [ComposePermission]

    def get_serializer_class(self):
        if self.action == 'list':
            return ComposeListSerializer
        elif self.action == 'version_history':
            return ComposeVersionSerializer
        elif self.action == 'statuses':
            return ComposeStatusSerializer
        elif self.action == 'custom_update':
            return ComposeCustomUpdateSerializer
        elif self.action == 'links':
            return ComposeLinkSerializer
        return ComposeSerializer

    def get_queryset(self):
        user = self.request.user
        permission_qs = user.permissions.filter(
            content_type_id=30
        )

        # Base queryset for author visibility
        queryset = Compose.objects.select_related(
            'author',
            'curator',
            'document_type',
            'document_sub_type',
            'status',
            'journal',
            'company',
            'sender',
        ).prefetch_related('files', 'approvers', 'signers').none()

        # Get allowed document types
        allowed_document_types = permission_qs.filter(
            document_type__isnull=False,
            document_sub_type__isnull=True,
            all_visible=True
        ).values_list('document_type_id', flat=True)

        # Get allowed document sub-types but ensure their document type is allowed
        allowed_document_sub_types = permission_qs.filter(
            document_sub_type__isnull=False,
            all_visible=True
        ).values_list('document_sub_type_id', flat=True)

        # Define filters
        permission_filters = Q()
        if allowed_document_types:
            permission_filters |= Q(document_type__in=allowed_document_types)
        if allowed_document_sub_types:
            permission_filters |= Q(document_sub_type__in=allowed_document_sub_types)

        # Apply the combined filter to the queryset
        if permission_filters:
            queryset = Compose.objects.filter(permission_filters)

        # Include user's own documents
        queryset = queryset | Compose.objects.filter(author_id=user.id)

        return queryset.order_by('-created_date').distinct()

    def get_object(self):
        queryset = Compose.objects.filter()

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
        current_user = get_current_user_id()

        if instance.author_id != current_user:
            message = get_response_message(request, 700)
            raise ValidationError2(message)

        if instance.status_id == get_compose_status_id(type='done'):
            message = get_response_message(request, 700)
            raise ValidationError2(message)

        return super(ComposeViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Delete related BusinessTrip records
        related_trips = BusinessTrip.objects.filter(
            Q(notice_id=instance.id) | Q(order_id=instance.id)
        )

        related_trips.delete()  # delete related trips first
        instance.delete()  # then delete the compose

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['get'], detail=True, url_path='version-history', serializer_class=ComposeVersionSerializer)
    def version_history(self, request, *args, **kwargs):
        instance = self.get_object()
        queryset = ComposeVersionModel.objects.filter(object_id=instance.id).order_by('created_date')
        serializer = ComposeVersionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False, url_path='statuses', serializer_class=ComposeStatusSerializer)
    def statuses(self, request, *args, **kwargs):
        queryset = ComposeStatus.objects.order_by('id')
        serializer = ComposeStatusSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=True, url_path='links', serializer_class=ComposeLinkSerializer)
    def links(self, request, *args, **kwargs):
        instance = self.get_object()
        from_composes = ComposeLink.objects.select_related('from_compose').filter(from_compose_id=instance.id)
        to_composes = ComposeLink.objects.select_related('to_compose').filter(to_compose_id=instance.id)
        data = {}
        data['from_composes'] = ComposeLinkSerializer(from_composes, many=True).data
        data['to_composes'] = ComposeLinkSerializer(to_composes, many=True).data

        return Response(data, status=status.HTTP_200_OK)

    def set_as_unsigned_if_changed(self, instance):
        """
        This function is responsible for setting the document as unsigned
        if the document has been changed after being signed.

        :param instance: The instance representing the task or item to be approved.
        """
        signers = Signer.objects.filter(compose_id=instance.id)
        if signers.exists():
            signers.update(is_signed=None)

        approvers = Approver.objects.filter(compose_id=instance.id)
        if approvers.exists():
            approvers.update(is_approved=None)
            signers.update(is_all_approved=False)

    def remove_curator_and_assistant(self, instance):
        """
        If the document has been changed,
        the curator and assistant will be removed.
        And the document will be sent to the approvers and signers again.
        """

        # Remove the curator from signers
        Signer.objects.filter(compose_id=instance.id,
                              user_id=instance.curator_id,
                              type='basic_signer').delete()

        # Get active assistants of the curator
        assistant_ids = list(instance.curator.assistants.
                             filter(is_active=True).
                             values_list('assistant_id', flat=True))

        # Remove assistants from approvers
        Approver.objects.filter(compose_id=instance.id,
                                user_id__in=assistant_ids).delete()

    def has_not_been_changed(self, old_text: str, new_text: str) -> bool:
        clean_old_text = clean_html(old_text)
        clean_new_text = clean_html(new_text)

        return remove_all_whitespaces(clean_old_text) == remove_all_whitespaces(clean_new_text)

    def _user_has_update_permission(self, instance, user_id):
        is_approver = instance.approvers.filter(user_id=user_id).exists()
        is_signer = instance.signers.filter(user_id=user_id).exists()

        return any([
            instance.author_id == user_id,
            is_approver,
            is_signer,
            instance.document_sub_type_id in [CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
                                              CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2]
        ])

    @action(methods=['put'], detail=True, url_path='custom-update',
            serializer_class=ComposeCustomUpdateSerializer)
    def custom_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        old_content = instance.content
        new_content = serializer.validated_data.get('content')
        user_id = get_current_user_id()

        if not self._user_has_update_permission(instance, user_id):
            message = get_response_message(request, 700)
            raise ValidationError2(message)

        text_changed = self.has_not_been_changed(old_content, new_content)
        if not text_changed:
            old_text = clean_html(instance.content)
            new_text = clean_html(new_content)
            create_compose_version.apply_async((instance.id, old_text, new_text, user_id), countdown=2)

            instance.content = new_content
            user_ip = get_user_ip(request)
            ct_id = get_content_type_id(instance)
            action_log.apply_async(
                (user_id, 'updated', '142',
                 ct_id, instance.id, user_ip),
                countdown=2)

            if instance.curator_id:
                self.remove_curator_and_assistant(instance)

            self.set_as_unsigned_if_changed(instance)

        instance.save()
        return Response({'message': 'ok'}, status=status.HTTP_200_OK)


class ApproveViewSet(viewsets.ModelViewSet):
    queryset = Approver.objects.all()
    serializer_class = ApproveSerializer
    filterset_class = ApproverFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return ApproveSerializer
        elif self.action == 'retrieve':
            return ApproveDetailSerializer
        elif self.action == 'approve' or self.action == 'reject':
            return ApproveListSerializer
        return ApproveSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related('compose', 'user',
                                                         'user__department',
                                                         'user__position').prefetch_related(
            'compose__files', 'compose__approvers', 'compose__signers')
        draft_status_id = get_compose_status_id(type='draft')
        queryset = queryset.filter(Q(user_id=self.request.user.id),
                                   Q(compose__is_deleted=False),
                                   ~Q(compose__status_id=draft_status_id),
                                   ~Q(compose__document_sub_type_id__in=[
                                       CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
                                       CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2
                                   ]))
        return queryset.order_by(F('is_approved').desc(nulls_last=False), '-created_date')

    def get_object(self):
        queryset = Approver.objects.filter()

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        if instance.read_time is None:
            instance.read_time = timezone.now()
            instance.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    def create_assistant(self, instance):
        """
        This function is responsible for creating an assistant as an approver
        who will review and potentially approve and send document to a curator for final signature.

        :param instance: The instance representing the task or item to be approved.
        """
        approvers = Approver.objects.filter(compose_id=instance.compose_id)
        user_id = get_current_user_id()

        if not all(approvers.values_list('is_approved', flat=True)):
            return

        try:
            assistant = instance.compose.curator.assistants.filter(is_active=True).first()
            if assistant and not Approver.objects.filter(user_id=assistant.assistant_id,
                                                         compose_id=instance.compose_id).exists():
                Approver.objects.create(user_id=assistant.assistant_id,
                                        compose_id=instance.compose_id,
                                        is_approved=None)

            if assistant and assistant.id == user_id:
                return

        except Exception as e:
            message = get_response_message(self.request, 777)
            raise ValidationError2(message, status_code=500)

        self.make_visible_to_signers(instance)

    def make_visible_to_signers(self, instance):
        """
        This function is responsible for making the document visible to signers
        after all approvers have approved the document.

        :param instance: The instance representing the task or item to be approved.
        """
        approvers = Approver.objects.filter(compose_id=instance.compose_id)
        if all(approvers.values_list('is_approved', flat=True)):
            Signer.objects.filter(compose_id=instance.compose_id).update(is_all_approved=True)

    def send_to_curator(self, instance, **kwargs):
        """
        Assistant prepares performers and sends the document to the curator.

        :param instance: The instance representing the task or item to be approved.
        """

        if not instance.compose.curator.assistants.filter(assistant_id=instance.user_id).exists():
            return

        approvers = Approver.objects.filter(compose_id=instance.compose_id)
        signers = Signer.objects.filter(compose_id=instance.compose_id)
        all_approved = all(approvers.values_list('is_approved', flat=True))
        all_signed = all(signers.values_list('is_signed', flat=True))

        if all_approved and all_signed:
            Signer.objects.create(
                user_id=instance.compose.curator_id,
                compose_id=instance.compose_id,
                is_all_approved=True,
                type='basic_signer',
                performers=kwargs.get('performers', None),
                resolution_text=kwargs.get('resolution_text', None),
                resolution_type=kwargs.get('resolution_type', None),
                deadline=kwargs.get('deadline', None),
            )

    @action(methods=['put'], detail=True,
            url_name='approve',
            url_path='approve',
            serializer_class=ApproveListSerializer)
    def approve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.is_approved is True:
            message = get_response_message(request, 613)
            raise ValidationError2(message)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.validated_data.get('comment')
        performers = serializer.validated_data.get('performers')
        resolution_text = serializer.validated_data.get('resolution_text')
        resolution_type = serializer.validated_data.get('resolution_type')
        deadline = serializer.validated_data.get('deadline')

        instance.is_approved = True
        instance.comment = comment
        instance.action_date = timezone.now()
        instance.save()

        # make the document visible to signers
        self.make_visible_to_signers(instance)

        if instance.is_approved and instance.compose.curator_id:
            self.send_to_curator(instance, performers=performers,
                                 resolution_text=resolution_text,
                                 resolution_type=resolution_type,
                                 deadline=deadline)

        # Set approval to decree together
        if instance.compose.document_sub_type_id == CONSTANTS.DOC_TYPE_ID.TRIP_NOTICE_V2 or CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_NOTICE_V2:
            decree_compose = ComposeLink.objects.filter(to_compose=instance.compose).first()
            self.approve_decree(decree_compose, instance.user_id)
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = get_content_type_id(instance.compose)
        action_log.apply_async(
            (user_id, 'created', '128', ct_id,
             instance.compose_id, user_ip, comment), countdown=2)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True, url_name='reject', url_path='reject', serializer_class=ApproveListSerializer)
    def reject(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance.is_approved is True:
            message = get_response_message(request, 609)
            raise ValidationError2(message)

        if instance.is_approved is False and instance.action_date:
            message = get_response_message(request, 608)
            raise ValidationError2(message)

        comment = serializer.validated_data.get('comment')
        instance.is_approved = False
        instance.comment = comment
        instance.action_date = timezone.now()
        instance.compose.status_id = ComposeStatus.objects.get(declined_from_approver=True).id
        instance.save()
        instance.compose.save()
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = get_content_type_id(instance.compose)
        action_log.apply_async(
            (user_id, 'created', '127', ct_id,
             instance.compose_id, user_ip, comment), countdown=2)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def approve_decree(self, decree_compose, user_id):
        if decree_compose:
            # Create user for decree and approve it
            now = timezone.now()
            Approver.objects.create(user_id=user_id,
                                    compose=decree_compose.from_compose,
                                    is_approved=True, action_date=now,
                                    read_time=now)


class SignerViewSet(viewsets.ModelViewSet):
    queryset = Signer.objects.all()
    serializer_class = SignerList2Serializer
    filterset_class = SignerFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return SignerList2Serializer
        elif self.action in ['sign', 'reject']:
            return SignerListSerializer
        return SignerDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related('compose', 'user',
                                                         'user__department',
                                                         'user__position',
                                                         'user__company',
                                                         'user__top_level_department',
                                                         'user__status',
                                                         'compose__document_type',
                                                         'compose__document_sub_type')
        draft_status_id = get_compose_status_id(type='draft')
        user_id = get_current_user_id()
        queryset = queryset.filter(Q(user_id=user_id),
                                   Q(is_all_approved=True),
                                   Q(compose__is_deleted=False),
                                   ~Q(compose__status_id=draft_status_id),
                                   ~Q(compose__document_sub_type_id__in=[
                                       CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
                                       CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2
                                   ]))

        return queryset.order_by(F('is_signed').desc(nulls_last=False), '-created_date')

    def get_object(self):
        queryset = Signer.objects.filter()

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        if instance.read_time is None:
            instance.read_time = timezone.now()
            instance.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True, url_name='reject', url_path='reject', serializer_class=SignerListSerializer)
    def reject(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance.is_signed is True:
            message = get_response_message(request, 609)
            raise ValidationError2(message)

        if instance.is_signed is False and instance.action_date:
            message = get_response_message(request, 608)
            raise ValidationError2(message)

        comment = serializer.validated_data.get('comment')
        instance.is_signed = False
        instance.comment = comment
        instance.action_date = timezone.now()
        instance.compose.status_id = ComposeStatus.objects.get(declined_from_signer=True).id
        instance.save()
        instance.compose.save()

        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = get_content_type_id(instance.compose)
        action_log.apply_async(
            (user_id, 'created', '141', ct_id,
             instance.compose_id, user_ip, comment), countdown=2)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True,
            url_name='sign',
            url_path='sign',
            serializer_class=SignerListSerializer)
    def sign(self, request, *args, **kwargs):
        """
        Sign the document by the signer.
        To sign the document signer must have the right to sign the document
        and EDS key must be provided.
        """
        instance = self.get_object()
        user_id = get_current_user_id()

        if instance.is_signed is True:
            message = get_response_message(request, 613)
            raise ValidationError2(message)

        if instance.is_all_approved in [False,
                                        None] and instance.compose.document_sub_type_id != CONSTANTS.DOC_TYPE_ID.ACT_SERVICE_CONTRACT_WORKS:
            message = get_response_message(request, 628)
            raise ValidationError2(message)

        if user_id != instance.user_id:
            message = get_response_message(request, 624)
            raise ValidationError2(message)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.validated_data.get('comment', None)
        pkcs7 = serializer.validated_data.get('pkcs7', None)
        performers = serializer.validated_data.get('performers', None)
        resolution_text = serializer.validated_data.get('resolution_text', None)
        resolution_type = serializer.validated_data.get('resolution_type', None)
        deadline = serializer.validated_data.get('deadline', None)
        info = None

        if os.getenv('ENVIRONMENT') == 'PROD' and user_id != 1:
            result, info = DigitalSignatureService(
                model=DigitalSignInfo,
                document=instance.compose.content,
                document_id=instance.compose_id,
                request=request,
                pkcs7=pkcs7,
                class_name=instance.compose.__class__.__name__,
            ).sign()

            if result != 'ok':
                return Response({'success': False, 'message': info}, status=status.HTTP_400_BAD_REQUEST)

        instance.is_signed = True
        instance.action_date = timezone.now()
        instance.performers = performers
        instance.resolution_text = resolution_text
        instance.resolution_type = resolution_type
        instance.deadline = deadline
        instance.certificate_info = info
        instance.is_all_approved = True
        instance.save()

        approvers_qs = Approver.objects.filter(
            compose_id=instance.compose_id,
            added_by_id=instance.user_id
        )

        # Approvers that did NOT approve or disapproved (delete them)
        approvers_qs.filter(
            Q(is_approved=False) | Q(is_approved__isnull=True)
        ).delete()

        # save user action to database
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = get_content_type_id(instance.compose)
        action_log.apply_async(
            (user_id, 'created', '140', ct_id,
             instance.compose_id, user_ip, comment), countdown=2)

        # create a signer for decree
        if instance.compose.document_sub_type_id in [CONSTANTS.DOC_TYPE_ID.TRIP_NOTICE_V2,
                                                     CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_NOTICE_V2,
                                                     CONSTANTS.DOC_TYPE_ID.BUSINESS_TRIP_NOTICE_FOREIGN]:
            decree_compose = ComposeLink.objects.filter(to_compose=instance.compose).first()
            self.sign_decree(decree_compose, instance.user_id,
                             info, instance.type, resolution_type,
                             resolution_text, deadline, performers)

        if instance.compose.document_sub_type_id == CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_NOTICE_V2:

            # find all business trips whose notice_id == instance.compose.id
            related_trips = BusinessTrip.objects.filter(notice_id=instance.compose.id)

            for trip in related_trips:
                if trip.parent_id:
                    BusinessTrip.objects.filter(id=trip.parent_id).update(is_active=True)

        # if the document type is not in the excluded list
        # and the user is not the curator
        # and the document has a curator
        # then send the document to the assistant of the curator
        # otherwise error might occur

        if (
                instance.type in ['signer', 'negotiator', 'invited']
                and instance.compose.curator_id
        ):
            # send the document to the assistant of the curator
            self.send_to_curator_assistant(instance)

        # register as the base document after all signers have signed the document
        register_document_after_signing(instance.compose, request, performers)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='add-approvers')
    def add_approvers(self, request):
        approver_ids = request.data.get('approvers', [])
        compose_id = request.data.get('compose_id')
        added_by = get_current_user_id()

        if not approver_ids or not compose_id:
            return Response(
                {"detail": "Both 'approvers' and 'compose_id' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = 0
        skipped = 0

        for user_id in approver_ids:
            exists = Approver.objects.filter(
                user_id=user_id,
                compose_id=compose_id,
                added_by_id=added_by
            ).exists()

            if exists:
                skipped += 1
                continue  # Skip if the current user already added this approver

            Approver.objects.create(
                user_id=user_id,
                compose_id=compose_id,
                added_by_id=added_by
            )

            created += 1

        return Response(
            {
                "detail": "Approver creation complete.",
                "created": created,
                "skipped": skipped
            },
            status=status.HTTP_201_CREATED
        )

    def sign_decree(self, decree_compose, user_id, info, type,
                    resolution_type, resolution_text, deadline, performers):
        if decree_compose:
            # Create user for decree and sign it
            now = timezone.now()
            Signer.objects.create(user_id=user_id,
                                  compose=decree_compose.from_compose,
                                  is_signed=True, action_date=now,
                                  read_time=now, is_all_approved=True,
                                  certificate_info=info,
                                  type=type,
                                  resolution_type=resolution_type,
                                  resolution_text=resolution_text,
                                  deadline=deadline,
                                  performers=performers)

    def send_to_curator_assistant(self, instance):
        """
        This function is responsible for sending the document to the assistant of the curator
        if the document has been signed by all signers.

        :param instance: The instance representing the task or item to be approved.
        """

        if self.are_all_signed_and_approved(instance.compose_id):
            # send the document to the assistant of the curator
            assistant = instance.compose.curator.assistants.filter(is_active=True).first()
            Approver.objects.create(user_id=assistant.assistant_id, compose_id=instance.compose_id, is_approved=None)

    def are_all_signed_and_approved(self, compose_id):
        """
        This function is responsible for checking
        if all signers and negotiators have signed the document.
        """
        signers = Signer.objects.filter(compose_id=compose_id)
        approvers = Approver.objects.filter(compose_id=compose_id)

        all_signed = all(signers.values_list('is_signed', flat=True))
        all_approved = all(approvers.values_list('is_approved', flat=True))

        return all_signed and all_approved


class ComposeVerifyViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Compose.objects.all()
    serializer_class = ComposeVerifySerializer
    lookup_field = 'check_id'
    permission_classes = [permissions.AllowAny, ]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if not instance.is_signed:
            message = get_response_message(request, 639)
            raise ValidationError2(message)

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=True, url_name='file', url_path='file')
    def file(self, request, *args, **kwargs):
        instance = self.get_object()
        file = instance.file

        if not file:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='file')
            raise ValidationError2(message)

        try:
            if file.year:
                object_name = f'{file.module}/{file.year}/{file.key}.{file.extension}'
            else:
                object_name = f'{file.module}/{file.key}.{file.extension}'
            minio_response = MINIO_CLIENT.get_object(MINIO_BUCKET_NAME, object_name)

            response = FileResponse(minio_response, content_type=file.content_type)
            response['Content-Disposition'] = f'attachment; filename="{file.name}"'
            response['Cache-Control'] = 'public, max-age=3600'
            return response
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=500)


class RestoreCompose(views.APIView):
    permission_classes = [permissions.IsAdminUser, ]

    def post(self, request, *args, **kwargs):
        compose_id = kwargs.get('compose_id')
        compose = get_object_or_404(Compose, id=compose_id, is_deleted=False)
        basic_signer = compose.signers.filter(type='basic_signer')
        performers = None
        if basic_signer.exists():
            performers = basic_signer.first().performers

        self.delete_related_documents(compose_id)
        time.sleep(1)

        register_document_after_signing(compose, request, performers)

        return Response({'message': 'ok'}, status=status.HTTP_200_OK)

    def delete_related_documents(self, compose_id):
        BaseDocument.objects.filter(compose_id=compose_id).delete()
        compose_link = ComposeLink.objects.filter(to_compose_id=compose_id).first()
        if compose_link:
            BaseDocument.objects.filter(compose_id=compose_link.from_compose_id).delete()


class IABSActionHistoryViewSet(viewsets.GenericViewSet,
                               mixins.ListModelMixin,
                               mixins.RetrieveModelMixin):
    queryset = (IABSActionHistory.objects.
                select_related(
        'compose',
        'compose__document_type',
        'compose__document_sub_type',
        'compose__company').
                order_by('-created_date'))
    serializer_class = IABSActionHistorySerializer
    filterset_class = IABSActionHistoryFilter

    @action(methods=['post'], detail=True, url_path='retry-action', serializer_class=IABSRetryActionSerializer)
    def retry_action(self, request, *args, **kwargs):
        instance = self.get_object()
        TRIP = 'trip'
        SENT = 'sent'
        ORDER = 'order'

        if instance.status == SENT:
            return Response({'message': 'Action already successful'}, status=status.HTTP_304_NOT_MODIFIED)

        try:
            service = IABSRequestService()
            request_body = instance.request_body

            if instance.type == ORDER:
                order_number = request_body.get('orderNumber')
                order_seria = request_body.get('orderSeria')

                if '/' in order_number:
                    request_body['orderNumber'] = order_seria
                    request_body['orderSeria'] = order_number

            if instance.type == TRIP:
                # Trip requires serializer to extract `order_id`
                serializer = self.get_serializer(instance, data=request.data)
                serializer.is_valid(raise_exception=True)
                order_id = serializer.validated_data.get('order_id')
                request_body['orderId'] = order_id

            response = service.retry_action(request_body, instance.endpoint)
            self.save_call_history(instance, response)

            if response.get('code') == 0:
                instance.status = SENT
                response_body = response.get('responseBody') or {}
                order_id = response_body.get('orderId')
                instance.save()

                if instance.type == ORDER:
                    # Fill the field with the order ID of trips action
                    self._update_iabs_id(instance.compose_id, order_id)

                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            else:
                return Response({'message': response.get('details'), 'body': request_body},
                                status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def save_call_history(self, instance, response):
        """
        This function saves the call history of the IABS request.
        """
        IABSRequestCallHistory.objects.create(
            action_history=instance,
            request_body=instance.request_body,
            response_body=response,
            caller_id=get_current_user_id(),
            response_code=response['code'],
            response_text=response.get('details'),
            status='sent' if response['code'] == 0 else 'failed',
            request_id=response.get('request_id')
        )

    def _update_iabs_id(self, compose_id, iabs_id):
        """
        This function updates the IABS ID in the action history
        for the given compose ID.
        :param compose_id: The ID of the compose.
        :param iabs_id: The IABS ID to be updated.
        """
        IABSActionHistory.objects.filter(compose_id=compose_id).update(iabs_id=iabs_id)


class IABSRequestCallHistoryViewSet(viewsets.GenericViewSet,
                                    mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin):
    queryset = IABSRequestCallHistory.objects.select_related('caller', 'action_history').order_by('-created_date')
    serializer_class = IABSRequestCallHistorySerializer
    filterset_fields = ['action_history', 'caller', 'request_id']
