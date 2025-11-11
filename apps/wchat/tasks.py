import logging

from django.db import connection
from django.utils import timezone

from apps.wchat.models import ChatMessage, Chat, ChatMember, MessageReceiver
from config.celery import app
from utils.constants import CONSTANTS
from utils.global_socket import (
    send_to_user_socket,
    send_to_group_chat_socket,
    send_to_private_chat_socket
)
from utils.utils import as_str


@app.task(max_retries=1, name='update_last_message_id_of_chat')
def update_last_message_id_of_chat(chat_id):
    """
    Updates the last message ID for a given chat by fetching the latest message.
    """

    try:
        with connection.cursor() as cursor:
            # Get the latest message ID for the chat
            cursor.execute(
                """
                SELECT id
                FROM wchat_chatmessage
                WHERE chat_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                [chat_id]
            )
            latest_message_id = cursor.fetchone()

            if latest_message_id:
                latest_message_id = latest_message_id[0]  # Extract ID from tuple

                # Perform the update only if needed
                cursor.execute(
                    """
                    UPDATE wchat_chat
                    SET last_message_id = %s
                    WHERE id = %s
                      AND last_message_id != %s
                    """,
                    [latest_message_id, chat_id, latest_message_id]
                )

    except Exception as e:
        logging.info(f"Error updating last message ID for chat {chat_id}: {e}")
        raise


@app.task(max_retries=1, name='send_socket_about_message_update')
def send_socket_about_message_update(message_id, chat_id):
    """
    Sends a socket event to notify users that a message has been updated.
    """
    # Use `select_related` to fetch related fields in a single query
    message = ChatMessage.objects.select_related('sender', 'chat').get(id=message_id)
    chat = message.chat
    members = list(ChatMember.objects.filter(chat_id=chat_id).values_list('user_id', flat=True))

    data = {
        'type': 'message_update',
        'text': message.text,
        'message_type': message.type,
        'sender': message.sender.dict(),
        'message_id': message_id,
        'chat_id': chat.id,
        'chat_type': chat.type,
        'uid': as_str(chat.uid),
    }

    if chat.type == CONSTANTS.CHAT.TYPES.GROUP:
        send_to_group_chat_socket(data, chat_id)
    elif chat.type == CONSTANTS.CHAT.TYPES.PRIVATE:
        send_to_private_chat_socket(data, chat_id)
    send_to_user_socket(data, *members)


@app.task(max_retries=1, name='send_socket_about_message_delete')
def send_socket_about_message_delete(message_id, message_type, chat_id, chat_type, **kwargs):
    """
    Sends a socket event to notify users that a message has been deleted.
    """

    members = list(ChatMember.objects.filter(chat_id=chat_id).values_list('user_id', flat=True))
    last_message_text = kwargs.get('last_message_text')
    last_message_date = kwargs.get('last_message_date')
    last_message_sender = kwargs.get('last_message_sender')

    data = {
        'type': 'message_deleted',
        'text': 'Message deleted',
        'message_id': message_id,
        'message_type': message_type,
        'chat_id': chat_id,
        'chat_type': chat_type,
        'last_message_text': last_message_text,
        'last_message_date': last_message_date,
        'last_message_sender': last_message_sender,
    }

    if chat_type == CONSTANTS.CHAT.TYPES.GROUP:
        send_to_group_chat_socket(data, chat_id)
    elif chat_type == CONSTANTS.CHAT.TYPES.PRIVATE:
        send_to_private_chat_socket(data, chat_id)
    send_to_user_socket(data, *members)


@app.task(max_retries=1, name='send_socket_about_new_group_chat')
def send_socket_about_new_group_chat(chat_id: int, members: list):
    """
    Sends a socket event to notify users that a new group chat has been created.
    """
    chat = Chat.objects.get(id=chat_id)

    data = {
        'type': 'new_group_chat',
        'chat_id': chat_id,
        'title': chat.title,
        'chat_type': chat.type,
        'uid': as_str(chat.uid),
    }

    send_to_user_socket(data, *members)


@app.task(max_retries=1, name='send_socket_about_chat_deleted')
def send_socket_about_chat_deleted(chat_id: int, chat_type: str, **kwargs):
    """
    Sends a socket event to notify users that a chat has been deleted.
    """
    members = kwargs.get('members')
    data = {
        'type': 'chat_deleted',
        'chat_id': chat_id,
        'chat_type': chat_type
    }

    send_to_user_socket(data, *members)

    return 'Chat deleted and users notified'


@app.task(max_retries=1, name='deliver_message')
def deliver_message(message_id: int, chat_id: int, sender_id: int):
    qs = ChatMember.objects.filter(chat_id=chat_id).exclude(user_id=sender_id)
    # Stream user_ids to avoid loading huge lists in memory
    rows = (
        MessageReceiver(
            message_id=message_id,
            receiver_id=uid,
            delivered=timezone.now(),
        )
        for uid in qs.values_list("user_id", flat=True).iterator(chunk_size=10000)
    )
    MessageReceiver.objects.bulk_create(rows, batch_size=10000, ignore_conflicts=True)


@app.task(max_retries=1, name='send_about_message_outside_chat')
def send_about_message_outside_chat(message_id: int):
    """
    Notifies users about a new message outside the chat.
    """
    message = ChatMessage.objects.get(id=message_id)
    chat = message.chat
    members = list(ChatMember.objects.filter(chat_id=chat.id).values_list('user_id', flat=True))

    data = {
        'type': 'new_chat_message',
        'text': message.text,
        'message_type': message.type,
        'sender': message.sender.simple_dict(),
        'message_id': message_id,
        'chat_id': chat.id,
        'chat_type': chat.type,
        'uid': as_str(chat.uid),
        'created_date': timezone.localtime(message.created_date).isoformat(),
    }

    send_to_user_socket(data, *members)


@app.task(max_retries=1, name='send_message_read')
def send_message_read(message_id: int, reader_id: int):
    """
    If user logins from multiple devices,
    ensure all devices are notified that the message has been read.
    """
    message = ChatMessage.objects.get(id=message_id)
    chat = message.chat
    members = list(ChatMember.objects.filter(chat_id=chat.id).values_list('user_id', flat=True))

    data = {
        'type': 'notify_message_read',
        'message_id': message_id,
        'user_id': reader_id,
        'chat_id': chat.id,
        'chat_type': chat.type,
        'uid': as_str(chat.uid),
    }

    if chat.type == CONSTANTS.CHAT.TYPES.GROUP:
        send_to_group_chat_socket(data, chat.id)
    elif chat.type == CONSTANTS.CHAT.TYPES.PRIVATE:
        send_to_private_chat_socket(data, chat.id)
    send_to_user_socket(data, *members)
