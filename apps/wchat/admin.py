from django.contrib import admin

from apps.wchat.models import (
    Chat,
    ChatMember,
    ChatMessage,
    ChatMessageReaction,
    ChatMessageFile,
    MessageReceiver,
)


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    fields = ['uid', 'type', 'title', 'created_date', 'created_by', 'deleted', 'deleted_time']
    list_display = ['id', 'type', 'title', 'deleted', 'created_date', 'created_by']
    search_fields = ['title', 'created_by__first_name', 'created_by__last_name']
    date_hierarchy = 'created_date'
    list_filter = ['type', 'created_date', 'deleted']
    readonly_fields = [
        'uid',
        'type',
        'title',
        'created_date',
        'modified_date',
        'created_by',
        'modified_by',
        # 'deleted',
        'deleted_time',
    ]


@admin.register(ChatMember)
class ChatMemberAdmin(admin.ModelAdmin):
    fields = ['user', 'chat', 'role', 'created_date']
    list_display = ['user', 'chat', 'role', 'on_mute', 'created_date']
    list_filter = ['role', 'created_date']
    date_hierarchy = 'created_date'
    search_fields = ['chat__title', 'user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['user', 'chat', 'role', 'created_date', 'modified_date', 'created_by', 'modified_by']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    fields = [
        'chat',
        'sender',
        'text',
        'replied_to',
        'edited',
        'deleted',
        'type',
        'created_date',
    ]
    list_display = ['sender', 'text', 'chat', 'edited', 'type', 'created_date']
    list_filter = ['edited', 'deleted', 'created_date']
    date_hierarchy = 'created_date'
    search_fields = ['sender__first_name', 'sender__last_name', 'chat__title', 'text']
    readonly_fields = [
        'chat',
        'sender',
        'text',
        'replied_to',
        'edited',
        'edited_time',
        'deleted',
        'deleted_time',
        'type',
        'created_date',
        'modified_date',
    ]


@admin.register(ChatMessageReaction)
class ChatMessageReactionAdmin(admin.ModelAdmin):
    fields = ['user', 'message', 'emoji', 'created_date']
    list_display = ['user', 'message', 'emoji', 'created_date']
    date_hierarchy = 'created_date'
    list_filter = ['created_date']
    search_fields = ['user__first_name', 'user__last_name', 'message__text']
    autocomplete_fields = ['user', 'message']
    readonly_fields = ['user', 'message', 'emoji', 'created_date', 'modified_date']


@admin.register(ChatMessageFile)
class ChatMessageFileAdmin(admin.ModelAdmin):
    fields = ['message', 'file', 'created_date']
    list_display = ['message', 'get_message_type', 'file', 'created_date']
    search_fields = ['message__text', 'file__name']
    readonly_fields = ['message', 'file', 'created_date']
    list_filter = ['created_date']
    date_hierarchy = 'created_date'

    def get_message_type(self, obj):
        return obj.message.type if obj.message.type else 'N/A'

    get_message_type.short_description = 'Message type'


@admin.register(MessageReceiver)
class MessageReceiverAdmin(admin.ModelAdmin):
    fields = ['message', 'receiver', 'delivered', 'read']
    list_display = ['message', 'receiver', 'delivered', 'read']
    search_fields = ['receiver__first_name', 'receiver__last_name', 'message__text']
    list_filter = ['read', 'delivered']
    date_hierarchy = 'delivered'
    readonly_fields = ['receiver', 'message', 'delivered', 'read', 're_read']
