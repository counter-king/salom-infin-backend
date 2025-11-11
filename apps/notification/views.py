import random

from django.db import transaction
from django.utils import timezone
from rest_framework import views, generics
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from utils.exception import ValidationError2, get_response_message
from utils.global_socket import send_to_user_socket
from .models import TelegramPairRequest, TelegramProfile
from .serializers import (
    ConfirmTelegramPairingSerializer,
    TelegramCallbackSerializer,
    TelegramUnlinkSerializer,
    TelegramProfileSerializer,
    SendTestMessageSerializer,
)
from .tasks import send_telegram_notification
from .telegram_client import TelegramClient
from .telegram_pairing import generate_short_token, compute_expiry, hash_token


class CreateTelegramPairRequestView(views.APIView):
    def post(self, request):
        user = request.user
        # token = generate_pairing_token(user.id)
        token = generate_short_token()
        token_hash = hash_token(token)
        expires_at = compute_expiry()

        if TelegramProfile.objects.filter(user=user, is_active=True).exists():
            raise ValidationError2(get_response_message(request, 899))

        pair_obj = TelegramPairRequest.objects.create(
            user=user,
            request_token=token_hash,
            expires_at=expires_at
        )
        bot_username = "salomapp_bot"
        deep_link = f"https://t.me/{bot_username}?start={token}"

        return Response({
            "deep_link": deep_link,
            "request_token": token,
            "expires_at": pair_obj.expires_at.isoformat(),
            "expires_in": int((pair_obj.expires_at - timezone.now()).total_seconds()),
        })


def generate_confirmation_code():
    return str(random.randint(100000, 999999))


class TelegramBotCallbackView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = TelegramCallbackSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_token = serializer.validated_data.get("request_token")
        telegram_id = serializer.validated_data.get("telegram_id")
        telegram_username = serializer.validated_data.get("telegram_username")
        phone = serializer.validated_data.get("telegram_phone")

        if not request_token:
            return Response({"message": "invalid token"}, status=400)

        token = hash_token(request_token)

        # payload = validate_pairing_token(request_token)
        # if payload is None:
        #     return Response({"message": "invalid_token"}, status=400)

        # DB dagi pending request ni olamiz
        try:
            pair_obj = TelegramPairRequest.objects.get(request_token=token)
        except TelegramPairRequest.DoesNotExist:
            return Response({"message": "not_found"}, status=404)

        if pair_obj.is_expired(timezone.now()):
            return Response({"message": "expired"}, status=400)

        if pair_obj.approved:
            return Response({"message": "already_approved"}, status=400)

        code = generate_confirmation_code()

        pair_obj.telegram_id = telegram_id
        pair_obj.telegram_username = telegram_username
        pair_obj.confirmation_code = code
        pair_obj.telegram_phone = phone
        pair_obj.save(update_fields=["telegram_id", "telegram_username", "confirmation_code", "telegram_phone"])
        broadcast = {
            "type": "need_telegram_confirmation",
            "request_token": request_token,
        }
        members = [pair_obj.user_id]
        send_to_user_socket(broadcast, *members)

        return Response({
            "confirmation_code": code
        })


class ConfirmTelegramPairingView(generics.GenericAPIView):
    serializer_class = ConfirmTelegramPairingSerializer

    def post(self, request):
        user = request.user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_token = serializer.validated_data.get("request_token")
        code_input = serializer.validated_data.get("confirmation_code")

        # payload = validate_pairing_token(request_token)
        if request_token is None:
            return Response({"message": "Недействительный токен"}, status=400)

        token = hash_token(request_token)
        try:
            pair_obj = TelegramPairRequest.objects.get(request_token=token, user=user)
        except TelegramPairRequest.DoesNotExist:
            return Response({"message": "Не найдено"}, status=404)

        if pair_obj.is_expired(timezone.now()):
            return Response({"message": "Истек срок действия QR"}, status=400)

        if pair_obj.approved:
            return Response({"message": "Уже одобрено"}, status=400)

        if not pair_obj.confirmation_code or pair_obj.confirmation_code != code_input:
            return Response({"message": "Неправильный код"}, status=400)

        if not pair_obj.telegram_id:
            return Response({"message": "Нет информации телеграмма"}, status=400)

        approved = 'denied'
        with transaction.atomic():
            tp_profile, created = TelegramProfile.objects.get_or_create(user=user, chat_id=pair_obj.telegram_id)
            tp_profile.telegram_id = pair_obj.telegram_id
            tp_profile.username = pair_obj.telegram_username
            tp_profile.phone = pair_obj.telegram_phone
            tp_profile.save()

            pair_obj.approved = True
            pair_obj.approved_at = timezone.now()
            pair_obj.save(update_fields=["approved", "approved_at"])
            approved = 'approved'

        telegram_client = TelegramClient()
        telegram_client.send_user_status(
            chat_id=pair_obj.telegram_id,
            code=approved
        )

        return Response({
            "status": "ok",
            "telegram_id": tp_profile.chat_id,
            "telegram_username": tp_profile.username,
        })


class UnlinkTelegramProfileView(GenericAPIView):
    serializer_class = TelegramUnlinkSerializer

    def post(self, request):
        user = request.user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        telegram_id = serializer.validated_data.get("telegram_id")
        try:
            tp_profile = TelegramProfile.objects.get(user=user, chat_id=telegram_id)
            tp_profile.delete()
            telegram_client = TelegramClient()
            telegram_client.send_user_status(
                chat_id=telegram_id,
                code='denied'
            )
            return Response({"status": "unlinked"})
        except TelegramProfile.DoesNotExist:
            return Response({"message": "not_linked"}, status=404)


class TelegramProfilesView(generics.ListAPIView):
    serializer_class = TelegramProfileSerializer

    def get_queryset(self):
        user = self.request.user
        return TelegramProfile.objects.filter(user=user)


class SendTestMessageView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SendTestMessageSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # client = TelegramClient()
        # result = client.send_message(serializer.validated_data)
        user_ids = serializer.validated_data.get("user_ids")
        template_key = serializer.validated_data.get("template_key")
        context = serializer.validated_data.get("context", {})
        message_type = serializer.validated_data.get("type")
        result = send_telegram_notification.apply_async(
            (user_ids, message_type, template_key, context)
        )
        return Response({
            "ok": True,
            "task_id": result.id,
            "status": "queued"
        }, status=202)
