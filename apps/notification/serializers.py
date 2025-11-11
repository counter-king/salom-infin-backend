from rest_framework import serializers

from apps.notification.models import TelegramProfile


class TelegramProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramProfile
        fields = ['id', 'user', 'chat_id', 'username',
                  'phone', 'is_active', 'language',
                  'created_date', 'modified_date']


class TelegramCallbackSerializer(serializers.Serializer):
    request_token = serializers.CharField(max_length=1000, required=False)
    telegram_id = serializers.IntegerField(required=False)
    telegram_username = serializers.CharField(required=False)
    telegram_phone = serializers.CharField(required=False)


class ConfirmTelegramPairingSerializer(serializers.Serializer):
    request_token = serializers.CharField(max_length=1000, required=False)
    confirmation_code = serializers.CharField(max_length=10, required=False)


class TelegramUnlinkSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField(required=False)


class TestMessageSerializer(serializers.Serializer):
    tg_id = serializers.IntegerField(required=False)
    message = serializers.CharField(max_length=4000, required=False)
    type = serializers.CharField(required=False)
    additional_data = serializers.JSONField(required=False, allow_null=True)


class SendTestMessageSerializer(serializers.Serializer):
    # messages = TestMessageSerializer(many=True, required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
    type = serializers.CharField(required=False)
    template_key = serializers.CharField(required=False)
    context = serializers.JSONField(required=False, allow_null=True)
