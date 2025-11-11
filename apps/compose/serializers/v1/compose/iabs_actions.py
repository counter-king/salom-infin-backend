from rest_framework import serializers

from apps.compose.models import (IABSActionHistory, IABSRequestCallHistory)
from utils.serializer import SelectItemField


class IABSActionHistorySerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'position', 'top_level_department', 'table_number',
                                        'company'],
                           read_only=True)
    compose = SelectItemField(model='compose.Compose',
                              extra_field=['document_type', 'document_sub_type',
                                           'register_number', 'created_date'],
                              read_only=True)

    class Meta:
        model = IABSActionHistory
        fields = [
            'id',
            'type',
            'request_id',
            'action',
            'compose',
            'content_type',
            'iabs_id',
            'object_id',
            'result',
            'status',
            'user',
        ]


class IABSRetryActionSerializer(serializers.Serializer):
    order_id = serializers.CharField(
        required=False, allow_null=True
    )


class IABSRequestCallHistorySerializer(serializers.ModelSerializer):
    caller = SelectItemField(model='user.User',
                             extra_field=['full_name', 'position', 'top_level_department', 'table_number',
                                          'company'],
                             read_only=True)

    class Meta:
        model = IABSRequestCallHistory
        fields = [
            'id',
            'action_history_id',
            'request_id',
            'caller',
            'requested_date',
            'status',
            'response_text',
            'response_code',
        ]
