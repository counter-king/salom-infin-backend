import os

from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.compose.filters import (
    NegotiatorFilter,
)
from apps.compose.models import (
    NegotiationType,
    NegotiationSubType,
    Negotiation,
    NegotiationInstance,
    Negotiator, )
from apps.compose.serializers import (
    NegotiateSerializer,
    NegotiationInstanceSerializer,
    NegotiationSerializer,
    NegotiationSubTypeSerializer,
    NegotiationTypeSerializer,
    NegotiatorSerializer,
)
from apps.compose.services import DigitalSignatureService
from apps.reference.models import DigitalSignInfo
from config.middlewares.current_user import get_current_user_id
from utils.exception import get_response_message, ValidationError2


class NegotiationTypeViewSet(viewsets.ModelViewSet):
    queryset = NegotiationType.objects.all()
    serializer_class = NegotiationTypeSerializer
    search_fields = ('name', 'description')

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('created_date')


class NegotiationSubTypeViewSet(viewsets.ModelViewSet):
    queryset = NegotiationSubType.objects.all()
    serializer_class = NegotiationSubTypeSerializer
    search_fields = ('name', 'description')
    filterset_fields = ('doc_type',)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('created_date')


class NegotiationViewSet(viewsets.GenericViewSet,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.CreateModelMixin,
                         mixins.UpdateModelMixin):
    queryset = Negotiation.objects.all()
    serializer_class = NegotiationSerializer
    filterset_fields = ('doc_type', 'for_new_users')

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = get_current_user_id()
        return queryset.filter(created_by_id=user_id).order_by('created_date')


class NegotiationInstanceViewSet(viewsets.GenericViewSet,
                                 mixins.ListModelMixin,
                                 mixins.RetrieveModelMixin):
    queryset = NegotiationInstance.objects.order_by('-created_date')
    serializer_class = NegotiationInstanceSerializer
    filterset_fields = ('negotiation', 'doc_type', 'doc_sub_type')


class NegotiatorViewSet(viewsets.ModelViewSet):
    queryset = Negotiator.objects.all()
    serializer_class = NegotiatorSerializer
    filterset_class = NegotiatorFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = get_current_user_id()
        return queryset.filter(user_id=user_id).order_by('created_date')

    def get_serializer_class(self):
        if self.action == 'sign':
            return NegotiateSerializer
        return NegotiatorSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        if instance.read_time is None:
            instance.read_time = timezone.now()
            instance.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=False, url_name='sign', url_path='sign', serializer_class=NegotiateSerializer)
    def sign(self, request, *args, **kwargs):
        user_id = get_current_user_id()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get('ids', [])
        pkcs7 = serializer.validated_data.get('pkcs7', None)

        negotiators = Negotiator.objects.filter(id__in=ids)

        for negotiator in negotiators:
            if negotiator.is_signed:
                raise ValidationError2(get_response_message(request, 613))

            if user_id != negotiator.user_id:
                raise ValidationError2(get_response_message(request, 624))

            info = None
            if os.getenv('ENVIRONMENT') == 'PROD' and user_id != 1:
                result, info = DigitalSignatureService(
                    model=DigitalSignInfo,
                    document=negotiator.negotiation.content,
                    document_id=negotiator.negotiation_id,
                    request=request,
                    pkcs7=pkcs7,
                    class_name=negotiator.__class__.__name__,
                ).sign()

                if result != 'ok':
                    return Response({'success': False, 'message': info}, status=status.HTTP_400_BAD_REQUEST)

            negotiator.is_signed = True
            negotiator.dsi_info = info
            negotiator.action_date = timezone.now()

        Negotiator.objects.bulk_update(negotiators, ['is_signed', 'action_date', 'dsi_info'])

        return Response({'status': 'success'}, status=status.HTTP_200_OK)
