import uuid

from django.db import models
from django.db.models import Max
from django.utils import timezone

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class Chat(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=15, choices=CONSTANTS.CHAT.TYPES.CHOICES)
    title = models.CharField(max_length=200, blank=True, null=True)
    last_message = models.ForeignKey('ChatMessage',
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='last_message')
    deleted = models.BooleanField(default=False)
    deleted_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return '{} - {} - {}'.format(self.id, self.type, self.created_by.full_name)


class ChatImage(BaseModel):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='images')
    image = models.ForeignKey("document.File", related_name="avatars",
                              null=True, on_delete=models.SET_NULL)
    is_placed = models.BooleanField(default=False)

    def __str__(self):
        return '{}'.format(self.chat.type)

    class Meta:
        ordering = ['-is_placed']


class ChatMember(BaseModel):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, related_name='chat_user')
    role = models.CharField(max_length=20,
                            choices=CONSTANTS.CHAT.ROLES.CHOICES,
                            default=CONSTANTS.CHAT.ROLES.MEMBER)
    on_mute = models.BooleanField(default=False)

    def __str__(self):
        return '{}'.format(self.user.full_name)

    class Meta:
        unique_together = ('chat', 'user')


class MessageQueryManager(models.Manager):

    def _get_base_queryset(self):
        return super(MessageQueryManager, self)._get_base_queryset()

    def get_queryset(self):
        return super(MessageQueryManager, self).get_queryset().filter(deleted=False)


class ChatMessage(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    sender = models.ForeignKey("user.User", on_delete=models.SET_NULL,
                               related_name="sender", null=True)
    receiver = models.ForeignKey("user.User", on_delete=models.SET_NULL,
                                 related_name="receiver", null=True,
                                 blank=True)
    replied_to = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True)
    text = models.TextField(null=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, null=True, related_name='messages')
    edited = models.BooleanField(default=False)
    edited_time = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)
    deleted_time = models.DateTimeField(null=True, blank=True)
    type = models.CharField(max_length=30, null=True,
                            choices=CONSTANTS.CHAT.MESSAGE_TYPES.CHOICES,
                            default=CONSTANTS.CHAT.MESSAGE_TYPES.DEFAULT)

    objects = MessageQueryManager()

    def __str__(self):
        return f'{self.id}'

    @classmethod
    def get_max_message_id(cls, chat_id):
        return cls.objects.filter(chat_id=chat_id, deleted=False).aggregate(Max('id'))

    def is_message_read(self):
        """
        Check if at least one recipient has read the message.
        """
        return MessageReceiver.objects.filter(message=self, read__isnull=False).exists()

    def dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'created_date': str(self.created_date),
            'sender': self.sender.dict(),
            'receiver': self.receiver.dict() if self.receiver else None,
            'replied_to': self.replied_to.dict() if self.replied_to else None,
            'type': self.type
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'text': self.text,
            'created_date': str(self.created_date),
            'sender': self.sender.dict(),
            'receiver': self.receiver.dict() if self.receiver else None,
            'replied_to': self.replied_to.dict() if self.replied_to else None,
            'type': self.type
        }


class ChatMessageFile(BaseModel):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.ForeignKey("document.File", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return ''.format(self.message.id)


class ChatMessageReaction(BaseModel):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True)
    emoji = models.CharField(max_length=50)

    def __str__(self):
        return '{}'.format(self.message.text)

    class Meta:
        unique_together = ('message', 'user')


class MessageReceiver(BaseModel):
    receiver = models.ForeignKey("user.User", null=True, on_delete=models.SET_NULL)
    message = models.ForeignKey(ChatMessage, null=True, blank=True, on_delete=models.CASCADE)
    delivered = models.DateTimeField(null=True)
    read = models.DateTimeField(null=True)
    re_read = models.DateTimeField(null=True)

    class Meta:
        unique_together = ("receiver", "message_id")

    def __str__(self):
        return '{}'.format(self.message_id)

    @classmethod
    def mark_as_read(cls, message_id, receiver_id):
        """
        Mark the message as read by the receiver.
        """
        cls.objects.create(message_id=message_id, receiver_id=receiver_id, read=timezone.now())

    @classmethod
    def deliver_message(cls, message_id, receiver_id):
        """
        Mark the message as delivered to the receiver.
        """
        cls.objects.create(message_id=message_id, receiver_id=receiver_id, delivered=timezone.now())
