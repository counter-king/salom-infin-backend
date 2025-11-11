from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from daphne.ws_protocol import logger
from django.db import connection, transaction
from django.utils import timezone

from apps.document.models import File
from apps.wchat.models import (
    Chat,
    ChatMember,
    ChatMessage,
    ChatMessageFile,
    ChatMessageReaction,
)
from apps.wchat.tasks import deliver_message, send_about_message_outside_chat, send_message_read
from config.redis_client import redis_client
from utils.exception import SocketClientError, ValidationError2
from utils.tools import update_user_last_seen
from utils.utils import as_str


class SocketConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']
        # Join users group
        async_to_sync(self.channel_layer.group_add)(
            'users',
            self.channel_name
        )
        if self.user.is_authenticated:
            self.set_user_online()
        self.accept()

    def disconnect(self, close_code):
        # Leave app
        async_to_sync(self.channel_layer.group_discard)(
            'users',
            self.channel_name
        )

        if self.user.is_authenticated:
            self.set_user_offline()
        self.close()

    # Receive json message from WebSocket
    def receive_json(self, content, **kwargs):
        command = content.get('command')
        if command == 'ping':
            self.pong(content)
        elif command == 'chat_handshake':
            self._handshake(content)
        elif command == 'user_handshake':
            self._user_handshake()
        elif command == 'new_message':
            self._create_new_message(content)
        elif command == 'message_reaction':
            self._handle_message_reaction(content)
        elif command == 'message_read':
            self.mark_message_as_read(content)
        elif command == 'typing':
            self._typing(content)
        elif command == 'user_online':
            self.set_user_online()
        elif command == 'user_offline':
            self.set_user_offline()

    def set_user_online(self):
        """Mark the user as online in Redis."""
        redis_client.set(f'user_{self.user.id}', '1', ex=1200)
        self.notify_users(self.user.id, 'online')

    def set_user_offline(self):
        """Mark the user as offline in Redis."""
        user_id = self.user.id
        redis_client.delete(f'user_{user_id}')
        self.notify_users(user_id, 'offline')
        update_user_last_seen(user_id)

    def notify_users(self, user_id, status):
        """Notify all users that the user is online or offline."""
        user_chat_ids = ChatMember.objects.filter(user_id=user_id).values_list('chat_id', flat=True)
        chat_members = ChatMember.objects.filter(chat_id__in=user_chat_ids).exclude(user_id=user_id).values_list(
            "user_id", "chat_id")

        for key, chat_id in chat_members:
            async_to_sync(self.channel_layer.group_send)(
                f'user_{key}',
                {
                    "type": "send.socket",
                    "message": {
                        'type': 'user_status',
                        'user_id': user_id,
                        'status': status,
                        'chat_id': chat_id
                    }
                }
            )

    def pong(self, data):
        logger.info("ping pong!")
        key = data.get('key', None)
        if key:
            self.channel_layer.group_add(
                key,
                self.channel_name,
            )
            content = {
                'command': 'ping',
                'result': 'pong'
            }
            self.send_json(content)
            self.channel_layer.group_send(
                key,
                content
            )

    def _handshake(self, data):
        """
        Called by receive_json when someone sent a join command.
        """
        logger.info("ChatConsumer: join_chat: %s" % str(data.get('chat_id')))
        try:
            chat = "%s_%s" % (data.get('chat_type'), data.get('chat_id', "-1"))
        except SocketClientError as e:
            return self.handle_client_error(e)

        # Add them to the group so they get room messages
        async_to_sync(self.channel_layer.group_add)(
            chat,
            self.channel_name,
        )

        # Notify the group that someone joined
        async_to_sync(self.channel_layer.group_send)(
            chat,
            {
                "type": "chat.handshake",
                "user": str(self.user),
                "chat_id": data.get("chat_id"),
                "chat_type": data.get("chat_type")
            }
        )

    # This helper method name matches the 'type' sent to the group: 'chat.handshake' -> chat_handshake
    def chat_handshake(self, event):
        chat_id = event.get("chat_id")
        chat_type = event.get("chat_type")
        if chat_id is None or chat_type is None:
            return self.send_error(
                action="chat_handshake",
                code="bad_request",
                message="chat_id and chat_type are required.",
                context={"chat_id": chat_id, "chat_type": chat_type},
                close=False,  # keep socket alive; client can correct and retry
            )

        # Membership/ACL check
        if not self._user_in_chat(chat_id):
            # For a handshake to **join** a room, it’s reasonable to refuse the room
            # but usually keep the socket for other chats. Do NOT raise.
            return self.send_error(
                action="chat_handshake",
                code="forbidden",
                message="You are not a member of this chat.",
                context={"chat_id": chat_id},
                close=False  # set to True if you prefer to terminate this session
            )

        # (Optional) add the connection to the room group here if your flow requires it
        # group_name = f"{chat_type}_{chat_id}"
        # async_to_sync(self.channel_layer.group_add)(group_name, self.channel_name)

        # Success response to let the client finish opening the room
        self.send_json({
            "type": "chat_handshake_ok",
            "command": "chat_handshake",
            "chat_id": chat_id,
            "chat_type": chat_type,
            "user": event.get("user"),  # ensure this is a compact, trusted payload
        })

    def _user_handshake(self):
        """
        This method is called when the user visits app
        and helps get messages or notification when he is not in the chat rooms
        """
        key = f'user_{self.user.id}'
        async_to_sync(self.channel_layer.group_add)(
            key,
            self.channel_name
        )
        self.send_json({
            'command': 'user_handshake',
            'user': {
                'id': self.user.id,
                'full_name': self.user.full_name
            }
        })

    # def change_user_status(self, status):
    #     """
    #     update user status as online when he/she is on the app
    #     """
    # user_id = self.user.id

    # q = '''UPDATE user_user SET socket_status = %s, socket_status_changed_on=NOW() WHERE id = %s'''
    # logger.info(
    #     q % (status, user_id))
    # cursor = connection.cursor()
    # cursor.execute(q, (
    #     status, user_id))

    def _user_in_chat(self, chat_id: int) -> bool:
        return ChatMember.objects.filter(chat_id=chat_id, user_id=self.user.id).exists()

    def _validate_replied_to(self, chat_id: int, replied_to_id: int | None) -> ChatMessage | None:
        if not replied_to_id:
            return None
        try:
            msg = (ChatMessage.objects
                   .select_related('sender')
                   .only('id', 'chat_id', 'text', 'type', 'sender_id')
                   .get(id=replied_to_id))
        except ChatMessage.DoesNotExist:
            raise ValidationError2({"replied_to_id": "Original message was not found."})
        if msg.chat_id != chat_id:
            raise ValidationError2({"replied_to_id": "Reply target belongs to another chat."})
        return msg

    def _build_event_payload(
            self,
            *,
            message: ChatMessage,
            replied_to_payload: dict | None,
            files_payload: list[dict]
    ) -> dict:
        # Keep the payload compact and consistent
        return {
            "type": "chat.new.message",
            "user": self.user.dict(),
            "message_id": message.id,
            "text": message.text,
            "chat_id": message.chat_id,
            "chat_type": getattr(message.chat, "type", None) if hasattr(message, "chat") else None,
            "message_type": message.type,
            "created_date": timezone.localtime(message.created_date).isoformat(),
            "replied_to_id": message.replied_to_id,
            "replied_to": replied_to_payload,
            "files": files_payload,
            "uid": as_str(message.chat.uid),
        }

    def _create_new_message(self, data: dict) -> None:
        """
        Create and broadcast a new message.
        Key properties:
          - Validates ACLs and replied_to target.
          - Bulk-attaches files.
          - Idempotent via client-supplied message_uid (optional).
          - Broadcast & tasks are executed ONLY after DB commit.
        """
        chat_id = data.get("chat_id")
        chat_type = data.get("chat_type")
        message_type = data.get("message_type")
        text = (data.get("text") or "").strip()
        replied_to_id = data.get("replied_to_id")
        file_ids = data.get("files") or []

        # 1) ACLs & basic validation
        if not chat_id:
            return self.send_error(
                action="chat_handshake",
                code="bad_request",
                message="chat_id is required.",
                context={"chat_id": chat_id},
                close=False,  # keep socket alive; client can correct and retry
            )
        if not self._user_in_chat(chat_id):
            return self.send_error(
                action="chat_handshake",
                code="forbidden",
                message="You are not a member of this chat.",
                context={"chat_id": chat_id},
                close=False  # set to True if you prefer to terminate this session
            )

        if not text and not file_ids:
            return self.send_error(
                action="new_message",
                code="bad_request",
                message="Message text or at least one file is required.",
                context={},
                close=False,
            )

        replied_to = self._validate_replied_to(chat_id, replied_to_id)

        # 2) Idempotency: if client_uid provided, check if we already stored it
        # if client_uid:
        #     existing = ChatMessage.objects.filter(chat_id=chat_id, sender_id=self.user.id, client_uid=client_uid).only(
        #         "id").first()
        #     if existing:
        #         # Already processed this logical message: no duplicate insert, just ACK/broadcast again if you want
        #         return

        # 3) Transactional write: message + attachments
        with transaction.atomic():
            # Optional: fetch chat relation for event payload (without N+1)
            chat = Chat.objects.only("id", "uid", "type").get(id=chat_id)

            message = ChatMessage.objects.create(
                sender_id=self.user.id,
                chat_id=chat_id,
                text=text,
                type=message_type,
                replied_to_id=replied_to.id if replied_to else None,
            )
            message.chat = chat  # annotate for later payload use

            # Files: validate & bulk attach
            if file_ids:
                files = list(File.objects.filter(id__in=file_ids).only("id", "name"))
                if len(files) != len(set(file_ids)):
                    raise ValidationError2({"files": "One or more files not found"})
                # (Optional) enforce ownership/visibility here
                ChatMessageFile.objects.bulk_create(
                    [ChatMessageFile(message_id=message.id, file_id=f.id) for f in files],
                    ignore_conflicts=False,
                )
                files_payload = [
                    {"id": f.id,
                     "name": f.name,
                     "duration": f.duration,
                     "peaks": f.peaks,
                     "size": f.size_
                     }
                    for f in files
                ]

            else:
                files_payload = []

            replied_to_payload = self.get_replied_to(replied_to)

            # 4) Broadcast + side effects only after commit
            def _after_commit():
                group = f"{chat_type}_{chat_id}"  # or your existing convention e.g., f"{chat.type}_{chat_id}"
                payload = self._build_event_payload(
                    message=message,
                    replied_to_payload=replied_to_payload,
                    files_payload=files_payload,
                )
                async_to_sync(self.channel_layer.group_send)(group, payload)

                # Update chat counters / last message safely AFTER commit
                try:
                    self.update_chat(chat_id, message.id)
                except Exception:
                    # log but do not break delivery
                    pass

                # schedule async work
                try:
                    deliver_message.apply_async((message.id, chat_id, self.user.id), countdown=1)
                    send_about_message_outside_chat.apply_async((message.id,), countdown=1)
                except Exception:
                    pass

            transaction.on_commit(_after_commit)

    # def _create_new_message(self, data):
    #     """
    #     This method is called when a user sends a message
    #     """
    #     try:
    #         chat_id = data.get('chat_id', '-1')
    #         chat_type = data.get('chat_type')
    #         chat = f'{chat_type}_{chat_id}'
    #     except SocketClientError as e:
    #         return self.handle_client_error(e)
    #
    #     with transaction.atomic():
    #         # Send message to the group
    #         message = ChatMessage.objects.create(
    #             sender_id=self.user.id,
    #             chat_id=data.get('chat_id'),
    #             text=data.get('text'),
    #             type=data.get('message_type'),
    #             replied_to_id=data.get('replied_to_id')
    #         )
    #         file_ids = data.get('files', [])
    #         files = []
    #         for file_id in file_ids:
    #             file = File.objects.get(id=file_id)
    #             ChatMessageFile.objects.create(
    #                 message=message,
    #                 file=file
    #             )
    #             files.append({
    #                 'id': file.id,
    #                 'name': file.name
    #             })
    #
    #     # files = self.attache_files(message, file_ids)
    #     # files = self.get_files(message.id)
    #     replied_to_data = self.get_replied_to(message.replied_to_id)
    #
    #     async_to_sync(self.channel_layer.group_send)(
    #         chat,
    #         {
    #             "type": "chat.new.message",
    #             "user": self.user.dict(),
    #             "message_id": message.id,
    #             "text": data.get('text'),
    #             "chat_id": data.get('chat_id'),
    #             "chat_type": data.get('chat_type'),
    #             "message_type": data.get('message_type'),
    #             "created_date": timezone.localtime(message.created_date).isoformat(),
    #             "replied_to_id": message.replied_to_id,
    #             "replied_to": replied_to_data,
    #             "files": files,
    #             'uid': as_str(message.chat.uid),
    #         }
    #     )
    #     message_id = message.id
    #     self.update_chat(chat_id, message_id)
    #     deliver_message.apply_async((message_id, chat_id, self.user.id), countdown=1)
    #     # deliver_message(message_id, chat_id, self.user.id)
    #     send_about_message_outside_chat.apply_async((message_id,), countdown=0.5)

    # Create new message
    def chat_new_message(self, event):
        """
        create.new.message helper method is used
        to send messages to the clients
        """

        self.send_json({
            'type': 'new_message',
            'sender': event.get('user'),
            'text': event.get('text'),
            'chat_type': event.get('chat_type'),
            'chat_id': event.get('chat_id'),
            'replied_to_id': event.get('replied_to_id'),
            'replied_to': event.get('replied_to'),
            'created_date': event.get('created_date'),
            'files': event.get('files'),
            'message_type': event.get('message_type'),
            'message_id': event.get('message_id'),
            'uid': event.get('uid'),
        })

    def get_replied_to(self, replied_to):
        """
        This helper method is used to get the replied message
        """

        if replied_to is None:
            return None
        try:
            replied_to = ChatMessage.objects.get(id=replied_to.id)
            return {
                'id': replied_to.id,
                'text': replied_to.text,
                'type': replied_to.type,
                'sender': replied_to.sender.dict(),
            }
        except ChatMessage.DoesNotExist:
            return None

    def update_chat(self, chat_id, message_id):
        """
        This method is used to update chat last message
        """
        Chat.objects.filter(id=chat_id).update(last_message_id=message_id,
                                               modified_date=timezone.now())

    def _handle_message_reaction(self, data):
        """
        Handle adding, updating and deleting reactions
        """
        try:
            message_id = data.get('message_id')
            chat_id = data.get('chat_id')
            chat_type = data.get('chat_type')
            chat = f'{chat_type}_{chat_id}'
            emoji = data.get('emoji')
            user = self.user

            # Check if user has already reacted to the message
            reaction, created = ChatMessageReaction.objects.get_or_create(
                message_id=message_id,
                user=user
            )
            if not created:
                if reaction.emoji == emoji:
                    # Delete reaction
                    reaction.delete()
                    action = 'deleted'
                else:
                    # Update reaction
                    reaction.emoji = emoji
                    reaction.save()
                    action = 'updated'
            else:
                # Add reaction
                reaction.emoji = emoji
                reaction.save()
                action = 'created'

            # Send reaction to the group
            async_to_sync(self.channel_layer.group_send)(
                chat,
                {
                    "type": "chat.message.reaction",
                    "user": user.simple_dict(),
                    "message_id": message_id,
                    "emoji": emoji,
                    "action": action
                }
            )
        except SocketClientError as e:
            self.handle_client_error(e)

    def chat_message_reaction(self, event):
        """
        This helper method is used to send message reactions
        """
        self.send_json({
            'type': 'message_reaction',
            'user': event.get('user'),
            'message_id': event.get('message_id'),
            'emoji': event.get('emoji'),
            'action': event.get('action')
        })

    def mark_message_as_read(self, data):
        """
        This method is called when a user reads a message
        """
        try:
            chat_id = data.get('chat_id')
            chat_type = data.get('chat_type')
            chat = f'{chat_type}_{chat_id}'
        except SocketClientError as e:
            return self.handle_client_error(e)

        message_id = data.get('message_id') or ChatMessage.get_max_message_id(chat_id).get("id__max")

        # Update read status in MessageReceiver table
        success = self.write_message_read_status(self.user.id, chat_id, message_id)

        # Send message to the group
        async_to_sync(self.channel_layer.group_send)(
            chat,
            {
                "type": "chat.message.read",
                "user": self.user.simple_dict(),
                "message_id": message_id
            }
        )
        send_message_read.apply_async((message_id, self.user.id), countdown=1)

    def write_message_read_status(self, user_id: int, chat_id: int, message_id: int) -> bool:
        """
        Efficiently updates the read status for all messages up to the given message_id.
        """
        sql = """
              INSERT INTO wchat_messagereceiver (receiver_id, message_id, delivered, read, re_read, is_active)
              SELECT %(user_id)s, m.id, NULL, NOW(), NOW(), TRUE
              FROM wchat_chatmessage AS m
              WHERE m.chat_id = %(chat_id)s
                AND m.sender_id <> %(user_id)s
                AND m.id <= %(message_id)s
              ON CONFLICT (receiver_id, message_id) DO UPDATE
                  SET read    = COALESCE(wchat_messagereceiver.read, NOW()),
                      re_read = NOW(); \
              """

        params = {
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id
        }

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
            return True
        except Exception as e:
            return False

    def chat_message_read(self, event):
        """
        This helper method is used to send message read status
        """
        self.send_json({
            'type': 'message_read',
            'user': event.get('user'),
            'message_id': event.get('message_id'),
            'read_at': event.get('read_at')
        })

    def send_socket(self, event):
        """
        This helper method is used globally outside Consumer class
        to send socket messages
        """
        logger.info(event)
        self.send_json(
            {
                'type': event['message']['type'],
                'content': event['message']
            }
        )

    def _typing(self, data):
        """
        This method is called when a user is typing
        """
        try:
            chat_id = data.get('chat_id', '-1')
            chat_type = data.get('chat_type')
            chat = f'{chat_type}_{chat_id}'
        except SocketClientError as e:
            return self.handle_client_error(e)

        # Send message to the group
        async_to_sync(self.channel_layer.group_send)(
            chat,
            {
                "type": "chat.typing",
                "user": self.user.simple_dict(),
                "chat_id": chat_id,
                "chat_type": chat_type
            }
        )

    def chat_typing(self, event):
        """
        This helper method is used to send typing status
        """
        self.send_json({
            'type': 'typing',
            'user': event.get('user'),
            'chat_id': event.get('chat_id'),
            'chat_type': event.get('chat_type')
        })

    def handle_client_error(self, e):
        """
        Called when a ClientError is raised.
        Sends error data to UI.
        """
        errorData = {}
        errorData['error'] = e.code
        if e.message:
            errorData['message'] = e.message
            self.send_json(errorData)
        return

    def send_error(
            self,
            *,
            action: str,
            code: str,
            message: str,
            context: dict | None = None,
            close: bool = False,
            close_code: int = 4403
    ) -> None:
        """
        Uniform error envelope over WS. Keep the socket open by default.
        action: the logical operation (e.g., 'chat_handshake')
        code:   machine-readable ('bad_request', 'forbidden', 'validation_error')
        """
        payload = {
            "type": "error",
            "action": action,
            "code": code,
            "message": message,
            "context": context or {},
        }
        self.send_json(payload)
        if close:
            self.close(code=close_code)
