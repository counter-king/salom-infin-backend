from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from apps.user.models import User, MySelectedContact
from apps.wchat.models import ChatMember
from config.middlewares.current_user import get_current_user_id
from utils.serializer import SelectItemField


class ContentTypeMixin(serializers.Serializer):
    content_type = serializers.SerializerMethodField()

    def get_content_type(self, obj):
        model = obj.__class__
        return ContentType.objects.get_for_model(model).id


class DashboardUserSerializer(serializers.ModelSerializer):
    company = SelectItemField(model='company.Company', extra_field=['id', 'name'], required=False)
    position = SelectItemField(model='company.Position', extra_field=['id', 'name'], required=False)
    top_level_department = SelectItemField(model='company.Department', extra_field=['id', 'name'], required=False)
    status = SelectItemField(model='user.UserStatus', extra_field=['id', 'name', 'code'], required=False)
    avatar = SelectItemField(model='document.File', extra_field=['id', 'url', 'name'], required=False)
    is_selected = serializers.SerializerMethodField(read_only=True)
    private_chat_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'avatar',
            'cisco',
            'color',
            'company',
            'department',
            'father_name',
            'first_name',
            'full_name',
            'id',
            'is_active',
            'last_name',
            'position',
            'status',
            'top_level_department',
            'is_selected',
            'is_user_online',
            'private_chat_id',
        ]

    def get_is_selected(self, obj):
        user_id = get_current_user_id()
        qs = MySelectedContact.objects.filter(contact_id=user_id, user_id=obj.id)
        return qs.exists()

    def get_private_chat_id(self, obj):
        user_id = get_current_user_id()
        qs = ChatMember.objects.select_related('chat').filter(created_by_id=user_id, user_id=obj.id)
        if qs.exists():
            return qs.first().chat.uid
        return None
