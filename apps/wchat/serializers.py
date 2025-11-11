from rest_framework import serializers

from apps.user.models import User
from apps.wchat.models import (
    Chat,
    ChatMessage,
    ChatMember,
    ChatImage,
    ChatMessageFile,
    ChatMessageReaction, MessageReceiver,
)
from config.middlewares.current_user import get_current_user_id
from config.redis_client import redis_client
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField
from utils.tools import get_or_none


class MembersSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    private_chat_uid = serializers.SerializerMethodField(read_only=True)
    _current_user_id = None

    @property
    def current_user_id(self):
        if not self._current_user_id:
            self._current_user_id = get_current_user_id()
        return self._current_user_id

    class Meta:
        model = ChatMember
        fields = [
            'id',
            'chat',
            'user',
            'role',
            'on_mute',
            'created_date',
            'modified_date',
            'private_chat_uid',
        ]

    def get_private_chat_uid(self, obj):
        """
        Retrieve the private chat ID between the current user and the member.
        """
        chat = Chat.objects.filter(
            type=CONSTANTS.CHAT.TYPES.PRIVATE,
            members__user_id=self.current_user_id,
        ).filter(
            members__user_id=obj.user_id
        ).distinct().first()

        return chat.uid if chat else None


class MuteUnmuteSerializer(serializers.Serializer):
    on_mute = serializers.BooleanField(required=False)


class MembersToAddSerializer(serializers.Serializer):
    members = serializers.ListField(child=serializers.IntegerField(), required=True)


class PrivateChatListSerializer(serializers.ModelSerializer):
    _current_user_id = None
    is_user_online = serializers.SerializerMethodField(read_only=True)
    title = serializers.SerializerMethodField(read_only=True)
    last_message = serializers.SerializerMethodField(read_only=True)
    unread_count = serializers.SerializerMethodField(read_only=True)
    on_mute = serializers.SerializerMethodField(read_only=True)
    first_unread_id = serializers.IntegerField(read_only=True, required=False, allow_null=True)

    @property
    def current_user_id(self):
        if not self._current_user_id:
            self._current_user_id = get_current_user_id()
        return self._current_user_id

    class Meta:
        model = Chat
        fields = [
            'id',
            'uid',
            'title',
            'type',
            'on_mute',
            'is_user_online',
            'first_unread_id',
            'unread_count',
            'last_message',
            'created_date',
        ]
        read_only_fields = ['type']

    def get_last_message(self, obj):
        if obj.last_message:
            return {
                'id': obj.last_message.id,
                'text': obj.last_message.text,
                'created_date': obj.last_message.created_date,
                'sender': obj.last_message.sender.dict(),
                'type': obj.last_message.type,
            }
        return None

    def _get_chat_member(self, chat_id, role=None, user_id=None):
        """Helper to retrieve and cache chat member by role or user_id."""
        if not hasattr(self, "_chat_member_cache"):
            self._chat_member_cache = {}

        cache_key = (chat_id, role, user_id)

        if cache_key not in self._chat_member_cache:
            queryset = ChatMember.objects.filter(chat_id=chat_id)

            if role is not None:
                queryset = queryset.filter(role=role)
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)

            self._chat_member_cache[cache_key] = queryset.select_related("user").first()

        return self._chat_member_cache[cache_key]

    def get_chat_member(self, obj):
        return self._get_chat_member(obj.id, role=CONSTANTS.CHAT.ROLES.MEMBER)

    def get_title(self, obj):
        """Determine the chat title based on the other participant."""
        chat_member = self.get_chat_member(obj)

        if chat_member and obj.created_by_id == self.current_user_id:
            return f"{chat_member.user.last_name} {chat_member.user.first_name}"
        return f"{obj.created_by.last_name} {obj.created_by.first_name}"

    def get_on_mute(self, obj):
        """Check if the current user is muted in the chat."""
        chat_member = self._get_chat_member(obj.id, user_id=self.current_user_id)
        return chat_member.on_mute if chat_member else False

    def get_is_user_online(self, obj):
        """Determine the online status of the other participant."""
        chat_member = self.get_chat_member(obj)

        if chat_member and obj.created_by_id == self.current_user_id:
            return self.get_user_online_status(chat_member.user_id)
        return self.get_user_online_status(obj.created_by_id)

    def get_user_online_status(self, user_id):
        """Check if a user is online in Redis."""
        return bool(redis_client.exists(f"user_{user_id}"))

    def get_unread_count(self, obj):
        # Prefer annotated value to avoid N+1 queries
        annotated = getattr(obj, "unread_count_annotated", None)
        if annotated is not None:
            return int(annotated)

        # Fallback (should not hit if annotation is present)
        return MessageReceiver.objects.filter(
            receiver_id=self.current_user_id,
            message__chat_id=obj.id,
            read__isnull=True,
            message__deleted=False,
        ).count()


class PrivateChatSerializer(PrivateChatListSerializer):
    members = MembersSerializer(read_only=True, required=False, many=True)
    member_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    first_unread_id = serializers.IntegerField(required=False, allow_null=True, read_only=True)

    class Meta(PrivateChatListSerializer.Meta):
        fields = PrivateChatListSerializer.Meta.fields + ['member_id', 'members', 'first_unread_id']

    def has_private_chat(self, current_user_id, member_id):
        """
        Checks if a private chat exists between the current user and the given member.

        :param current_user_id: ID of the current user
        :param member_id: ID of the other user
        :return: Chat instance if exists, else None
        """
        private_chat = Chat.objects.filter(
            type=CONSTANTS.CHAT.TYPES.PRIVATE,  # Ensure it's a private chat
            members__user_id=current_user_id
        ).filter(
            members__user_id=member_id  # Check if the other user is also a member
        ).distinct().first()

        return private_chat

    def validate(self, attrs):
        request = self.context.get('request', None)
        member_id = attrs.get('member_id', None)

        if not member_id:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='member')
            raise ValidationError2(msg)

        if member_id == self.current_user_id:
            msg = get_response_message(request, 626)
            raise ValidationError2(msg)

        if self.has_private_chat(self.current_user_id, member_id):
            msg = get_response_message(request, 627)
            raise ValidationError2(msg)

        return attrs

    def get_title(self, obj):
        qs = ChatMember.objects.filter(chat_id=obj.id, role=CONSTANTS.CHAT.ROLES.MEMBER).first()
        if obj.created_by_id == self.current_user_id:
            return f'{qs.user.last_name} {qs.user.first_name}'
        return f'{obj.created_by.last_name} {obj.created_by.first_name}'

    def create(self, validated_data):
        members = validated_data.pop('members', [])
        member_id = validated_data.pop('member_id', None)
        instance = super(PrivateChatSerializer, self).create(validated_data)
        instance.type = CONSTANTS.CHAT.TYPES.PRIVATE
        instance.save()

        ChatMember.objects.create(chat_id=instance.id, user_id=member_id, role=CONSTANTS.CHAT.ROLES.MEMBER)
        ChatMember.objects.create(chat_id=instance.id, user_id=self.current_user_id, role=CONSTANTS.CHAT.ROLES.OWNER)

        return instance


class GroupChatImagesSerializer(serializers.ModelSerializer):
    image = SelectItemField(model="document.File", extra_field=['id', 'url', 'name'], required=False)

    class Meta:
        model = ChatImage
        fields = [
            'id',
            'is_placed',
            'image',
        ]


class GroupChatListSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=100, required=True)
    last_message = serializers.SerializerMethodField(read_only=True)
    images = GroupChatImagesSerializer(required=False, many=True)
    unread_count = serializers.SerializerMethodField(read_only=True)
    on_mute = serializers.SerializerMethodField(read_only=True)
    first_unread_id = serializers.IntegerField(read_only=True, required=False, allow_null=True)

    _current_user_id = None

    @property
    def current_user_id(self):
        if not self._current_user_id:
            self._current_user_id = get_current_user_id()
        return self._current_user_id

    class Meta:
        model = Chat
        fields = [
            'id',
            'uid',
            'title',
            'type',
            'on_mute',
            'first_unread_id',
            'images',
            'last_message',
            'created_date',
            'unread_count',
        ]
        read_only_fields = ['type', 'last_message']

    def get_last_message(self, obj):
        if obj.last_message:
            return {
                'id': obj.last_message.id,
                'text': obj.last_message.text,
                'created_date': obj.last_message.created_date,
                'sender': obj.last_message.sender.dict(),
                'type': obj.last_message.type,
            }
        return None

    def get_unread_count(self, obj):
        """Retrieve the unread message count for the current user."""

        # Prefer annotated value to avoid N+1 queries
        annotated = getattr(obj, "unread_count_annotated", None)
        if annotated is not None:
            return int(annotated)

        return MessageReceiver.objects.filter(
            receiver_id=self.current_user_id,
            message__chat_id=obj.id,
            read__isnull=True,
            message__deleted=False,
        ).count()

    def get_on_mute(self, obj):
        """Check if the current user is muted in the chat."""
        chat_member = ChatMember.objects.filter(chat_id=obj.id, user_id=self.current_user_id).first()
        return chat_member.on_mute if chat_member else False


class GroupChatSerializer(GroupChatListSerializer):
    created_by = SelectItemField(model="user.User",
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    members_id = serializers.ListField(required=False, write_only=True, child=serializers.IntegerField())
    members = MembersSerializer(read_only=True, required=False, many=True)
    first_unread_id = serializers.IntegerField(read_only=True, required=False, allow_null=True)

    class Meta(GroupChatListSerializer.Meta):
        fields = GroupChatListSerializer.Meta.fields + ['created_by', 'members_id', 'members', 'first_unread_id']

    def validate(self, attrs):
        request = self.context.get('request', None)
        members_id = attrs.get('members_id', [])
        images = attrs.get('images', [])

        if not members_id and request.method == 'POST':
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='member')
            raise ValidationError2(msg)

        for member_id in members_id:
            get_or_none(User, request=request, id=member_id)

        for image in images:
            if image and image.get('image').extension.lower() not in ['jpg', 'jpeg', 'png']:
                msg = get_response_message(request, 654)
                raise ValidationError2(msg)

        return attrs

    def create(self, validated_data):
        members = validated_data.pop('members', [])
        members_id = validated_data.pop('members_id', [])
        images = validated_data.pop('images', [])
        instance = super(GroupChatSerializer, self).create(validated_data)
        instance.type = CONSTANTS.CHAT.TYPES.GROUP
        instance.save()

        for image_data in images:
            file = image_data.get('image', None)
            ChatImage.objects.create(chat_id=instance.id, image=file, is_placed=True)

        return instance

    def update(self, instance, validated_data):
        members = validated_data.pop('members', [])
        members_id = validated_data.pop('members_id', [])
        images = validated_data.pop('images', [])
        instance = super(GroupChatSerializer, self).update(instance, validated_data)
        self.update_group_images(instance, images)

        return instance

    def update_group_images(self, instance, images):
        """
        Update the images of a group chat without creating duplicates.
        """
        existing_images = ChatImage.objects.filter(chat_id=instance.id)
        existing_image_set = {img.image for img in existing_images}  # Store existing image objects

        new_images_set = {img_data['image'] for img_data in images if img_data.get('image')}  # Extract new images

        # Find images to delete (those that exist but are not in the new list)
        images_to_delete = existing_images.exclude(image__in=new_images_set)
        images_to_delete.delete()

        # Add only new images
        for image_data in images:
            file = image_data.get('image', None)
            if file and file not in existing_image_set:  # Check actual file object
                ChatImage.objects.create(chat_id=instance.id, image=file, is_placed=True)


class ChatSearchSerializer(serializers.ModelSerializer):
    image = SelectItemField(model="document.File", extra_field=['url', 'name'], required=False)
    title = serializers.SerializerMethodField(read_only=True)
    members = MembersSerializer(read_only=True, required=False, many=True)

    class Meta:
        model = Chat
        fields = [
            'id',
            'image',
            'title',
            'type',
            'members',
        ]

    def get_title(self, obj):
        if obj.type == CONSTANTS.CHAT.TYPES.PRIVATE:
            qs = ChatMember.objects.filter(chat_id=obj.id, role=CONSTANTS.CHAT.ROLES.MEMBER).first()
            return f'{qs.user.first_name} {qs.user.last_name}'
        return obj.title


class MessageFilesSerializer(serializers.ModelSerializer):
    file = SelectItemField(model="document.File",
                           extra_field=['id', 'url', 'name', 'peaks', 'duration', 'size_'],
                           required=False)

    class Meta:
        model = ChatMessageFile
        fields = [
            'id',
            'file',
        ]


class MessageReactionSerializer(serializers.ModelSerializer):
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'status', 'cisco', 'avatar', ],
                           read_only=True)

    class Meta:
        model = ChatMessageReaction
        fields = [
            'id',
            'user',
            'emoji',
            'created_date',
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = SelectItemField(model="user.User",
                             extra_field=['full_name', 'first_name', 'last_name',
                                          'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                          'top_level_department', 'department', 'company', 'email'],
                             read_only=True)
    replied_to = serializers.SerializerMethodField(read_only=True)
    attachments = MessageFilesSerializer(required=False, many=True, read_only=True)
    reactions = MessageReactionSerializer(required=False, many=True, read_only=True)
    is_read = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'sender',
            'attachments',
            'replied_to',
            'is_read',
            'text',
            'chat',
            'edited',
            'edited_time',
            'type',
            'created_date',
            'reactions',
        ]
        read_only_fields = [
            'type',
            'edited',
            'created_date',
            'edited_time',
        ]

    def get_is_read(self, obj):
        annotated = getattr(obj, "is_read_annotated", None)
        return bool(annotated) if annotated is not None else obj.is_message_read()

    def get_replied_to(self, obj):
        """
        Returns the message that the current message is replied to.
        Replace the message with custom text if it has been deleted.
        """
        if obj.replied_to:
            return {
                'id': obj.replied_to.id,
                'text': obj.replied_to.text if not obj.replied_to.deleted else 'Message deleted',
                'created_date': str(obj.replied_to.created_date),
                'sender': obj.replied_to.sender.dict(),
                'deleted': obj.replied_to.deleted,
            }
        return None


class MessageLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'text', 'created_date', 'type']


class ChatMessageFileSerializer(serializers.ModelSerializer):
    attachments = MessageFilesSerializer(required=False, many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'text',
            'created_date',
            'attachments',
        ]


class MessagePageSerializer(serializers.Serializer):
    page_size = serializers.IntegerField(required=False)
    message_id = serializers.IntegerField(required=False)
    chat_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        request = self.context.get('request', None)
        page_size = attrs.get('page_size', None)
        message_id = attrs.get('message_id', None)
        chat_id = attrs.get('chat_id', None)

        if not page_size:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='page_size')
            raise ValidationError2(msg)

        if not message_id:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='message_id')
            raise ValidationError2(msg)

        if not chat_id:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='chat_id')
            raise ValidationError2(msg)

        return attrs
