from typing import Optional

from django.db import connection, transaction
from django.db.models import OuterRef, Exists, Prefetch, Subquery, IntegerField, Value, Count, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, views, status, mixins, generics
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import CursorPagination, Cursor
from rest_framework.response import Response

from apps.docflow.serializers.docflow import SimpleResponseSerializer
from apps.user.models import User
from apps.wchat.filters import MessageLinkFilter
from apps.wchat.models import Chat, ChatMember, ChatMessage, ChatImage, ChatMessageFile, ChatMessageReaction, \
    MessageReceiver
from apps.wchat.pagination import MessageCursorPagination
from apps.wchat.serializers import (
    PrivateChatSerializer,
    PrivateChatListSerializer,
    GroupChatSerializer,
    GroupChatListSerializer,
    MembersToAddSerializer,
    MessageSerializer,
    GroupChatImagesSerializer, MessageLinkSerializer, ChatMessageFileSerializer, MuteUnmuteSerializer,
    MessagePageSerializer,
)
from apps.wchat.tasks import (
    update_last_message_id_of_chat,
    send_socket_about_message_update,
    send_socket_about_message_delete,
    send_socket_about_new_group_chat,
    send_socket_about_chat_deleted,
)
from config.middlewares.current_user import get_current_user_id
from utils.constants import CONSTANTS
from utils.exception import ValidationError2, get_response_message


class PrivetChatViewSet(viewsets.ModelViewSet):
    serializer_class = PrivateChatSerializer
    lookup_field = 'uid'

    def get_serializer_class(self):
        if self.action == 'list':
            return PrivateChatListSerializer
        return self.serializer_class

    def base_queryset(self):
        return Chat.objects.filter(
            type=CONSTANTS.CHAT.TYPES.PRIVATE,
            deleted=False,
        ).order_by('-modified_date')

    def get_queryset(self):
        user_id = get_current_user_id()

        # ---- Subqueries (used in both list and retrieve)
        first_unread_subq = (
            MessageReceiver.objects
            .filter(
                receiver_id=user_id,
                read__isnull=True,
                message__deleted=False,
                message__chat_id=OuterRef('pk'),
            )
            .order_by('message__created_date', 'message__id')
            .values('message_id')[:1]
        )

        unread_count_subq = (
            MessageReceiver.objects
            .filter(
                receiver_id=user_id,
                read__isnull=True,
                message__deleted=False,
                message__chat_id=OuterRef('pk'),
            )
            .values('message__chat_id')
            .annotate(c=Count('id'))
            .values('c')[:1]
        )

        q = (
            self.base_queryset()
            .filter(members__user_id=user_id)  # membership
            .annotate(
                first_unread_id=Subquery(first_unread_subq, output_field=IntegerField()),
                unread_count_annotated=Coalesce(Subquery(unread_count_subq), Value(0)),
            )
            .distinct()
        )

        # For LIST only, keep original behavior: require at least one message
        if self.action == 'list':
            q = q.filter(messages__isnull=False)

        return q

    def retrieve(self, request, uid=None, *args, **kwargs):
        chat = get_object_or_404(self.get_queryset(), uid=uid, type=CONSTANTS.CHAT.TYPES.PRIVATE)
        serializer = self.get_serializer(chat)
        return Response(serializer.data)

    def destroy(self, request, uid=None, *args, **kwargs):
        instance = get_object_or_404(Chat, uid=uid, type=CONSTANTS.CHAT.TYPES.PRIVATE)
        user_id = get_current_user_id()

        # Ensure the current user is the owner of the chat
        if not ChatMember.objects.filter(chat=instance, user_id=user_id).exists():
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        members = list(ChatMember.objects.filter(chat=instance).values_list('user_id', flat=True))

        # Notify users about the chat deletion via WebSocket
        send_socket_about_chat_deleted.apply_async((instance.id, instance.type), {'members': members}, countdown=1)

        # Delete the chat
        self.perform_destroy(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupChatViewSet(viewsets.ModelViewSet):
    serializer_class = GroupChatSerializer
    lookup_field = 'uid'

    def get_serializer_class(self):
        if self.action == 'list':
            return GroupChatListSerializer
        return self.serializer_class

    def base_queryset(self):
        return Chat.objects.filter(
            type=CONSTANTS.CHAT.TYPES.GROUP,
            deleted=False,
        ).order_by('-modified_date')

    def get_queryset(self):
        user_id = get_current_user_id()
        # q = super(GroupChatViewSet, self).get_queryset()
        # q = q.filter(members__user_id__in=[user_id])

        # ---- Annotate first_unread_id (oldest unread for this user in each chat)
        first_unread_subq = (
            MessageReceiver.objects
            .filter(
                receiver_id=user_id,
                read__isnull=True,
                message__deleted=False,
                message__chat_id=OuterRef('pk'),
            )
            .order_by('message__created_date', 'message__id')
            .values('message_id')[:1]
        )

        # ---- Annotate unread_count to avoid N+1 in serializer
        unread_count_subq = (
            MessageReceiver.objects
            .filter(
                receiver_id=user_id,
                read__isnull=True,
                message__deleted=False,
                message__chat_id=OuterRef('pk'),
            )
            .values('message__chat_id')
            .annotate(c=Count('id'))
            .values('c')[:1]
        )

        q = (
            self.base_queryset()
            .filter(members__user_id=user_id)  # membership
            .annotate(
                first_unread_id=Subquery(first_unread_subq, output_field=IntegerField()),
                unread_count_annotated=Coalesce(Subquery(unread_count_subq), Value(0)),
            )
            .distinct()
        )

        return q

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        chat_members = request.data.get('members_id', None)
        user_id = get_current_user_id()

        if chat_members:
            if user_id not in chat_members:
                chat_members.append(user_id)

            for member_id in chat_members:
                member = ChatMember()
                member.chat_id = instance.id
                member.user_id = member_id
                if member_id == user_id:
                    member.role = CONSTANTS.CHAT.ROLES.OWNER
                else:
                    member.role = CONSTANTS.CHAT.ROLES.MEMBER
                member.save()

        # Notify users about the new chat via WebSocket
        send_socket_about_new_group_chat.apply_async((instance.id, chat_members), countdown=1)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    @action(detail=True, methods=['post'],
            url_path='add-members', url_name='add_members',
            serializer_class=MembersToAddSerializer)
    def add_members(self, request, uid=None, *args, **kwargs):
        """
        Add members to a group chat.
        - Auth: require OWNER (or adjust to allow ADMIN too).
        - Validates user ids, dedupes, skips already-in members.
        - Concurrency-safe with UNIQUE constraint + ignore_conflicts.
        - Emits notifications only after the transaction commits.
        - Returns a structured outcome: added_ids, skipped_* buckets.
        """
        chat = self.get_object()
        user_id = get_current_user_id()

        # 1) Authorization (adjust if ADMINS should also be allowed)
        is_owner = ChatMember.objects.filter(
            chat_id=chat.id,
            user_id=user_id,
            role=CONSTANTS.CHAT.ROLES.OWNER,
        ).exists()

        if not is_owner:
            msg = get_response_message(request, 651)  # your existing helper
            return Response(msg, status=status.HTTP_403_FORBIDDEN)

        # 2) Parse & validate payload with the action’s serializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_ids = serializer.validated_data.get("members", []) or []

        # Deduplicate, enforce ints
        try:
            candidate_ids = list({int(u) for u in input_ids})
        except (TypeError, ValueError):
            return Response({"message": ["All ids must be integers."]}, status=400)

        if not candidate_ids:
            msg = get_response_message(request, 653)  # “no members provided”
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        # 3) Filter out already-in members
        existing_ids = set(
            ChatMember.objects.filter(chat_id=chat.id, user_id__in=candidate_ids)
            .values_list("user_id", flat=True)
        )
        to_add_ids = [uid for uid in candidate_ids if uid not in existing_ids]

        # 4) Validate user existence / tenancy (avoid leaking which users exist if needed)
        # If you have User model and tenant/org, check both here.
        valid_user_ids = set(
            User.objects.filter(id__in=to_add_ids).values_list("id", flat=True)
        )
        skipped_invalid = [uid for uid in to_add_ids if uid not in valid_user_ids]
        to_add_ids = [uid for uid in to_add_ids if uid in valid_user_ids]

        MAX_MEMBERS = 500
        current_count = ChatMember.objects.filter(chat_id=chat.id).count()
        if current_count + len(to_add_ids) > MAX_MEMBERS:
            return Response({"message": "Chat member limit exceeded."}, status=400)

        if not to_add_ids and not existing_ids:
            # Nothing to do at all
            return Response({
                "status": "success",
                "chat_id": chat.id,
                "added_ids": [],
                "skipped_already_members": [],
                "skipped_invalid_users": skipped_invalid,
                "requested_count": len(candidate_ids),
            }, status=status.HTTP_200_OK)

        # 5) Concurrency-safe insert (ignore_conflicts + UNIQUE(chat_id, user_id))
        with transaction.atomic():
            ChatMember.objects.bulk_create(
                [
                    ChatMember(
                        chat_id=chat.id,
                        user_id=uid,
                        role=CONSTANTS.CHAT.ROLES.MEMBER,
                    )
                    for uid in to_add_ids
                ],
                ignore_conflicts=True,  # safe under races; duplicates are ignored at DB level
            )
            # Re-check actual additions (in case some were inserted concurrently)
            actually_added = set(
                ChatMember.objects.filter(chat_id=chat.id, user_id__in=to_add_ids)
                .values_list("user_id", flat=True)
            )
            added_ids = sorted(actually_added - existing_ids)  # new entries only
            skipped_already = sorted(existing_ids | (set(to_add_ids) - actually_added))

            # 6) Notify after commit (Channels/Celery)
            def _after_commit():
                try:
                    # If you push via Celery task:
                    send_socket_about_new_group_chat.apply_async((chat.id, added_ids), countdown=1)
                    # Or directly via Channels group_send, if you prefer
                except Exception:
                    pass

            transaction.on_commit(_after_commit)

        message = get_response_message(request, 807)
        message['chat_id'] = chat.id
        message['added_ids'] = added_ids
        message['skipped_already_members'] = skipped_already
        message['skipped_invalid_users'] = skipped_invalid
        message['requested_count'] = len(candidate_ids)
        return Response(message, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path='remove-members',
        url_name='remove_members',
        serializer_class=MembersToAddSerializer
    )
    def remove_members(self, request, uid=None, *args, **kwargs):
        """
        Remove members from an existing group chat.
        - Only OWNER can remove members (adjust allowed_roles if needed).
        - Will not remove chat owners.
        - Will not remove the requester (owner) via this endpoint.
        - Returns a structured outcome instead of generic 400s.
        """
        chat = self.get_object()
        user_id = get_current_user_id()

        # 1) Authorization: must be OWNER in this chat
        is_owner = ChatMember.objects.filter(
            chat_id=chat.id,
            user_id=user_id,
            role=CONSTANTS.CHAT.ROLES.OWNER,
        ).exists()
        if not is_owner:
            # Your helper message preserved
            message = get_response_message(request, 651)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        # Get user IDs from request
        serializer = MembersToAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member_ids = serializer.validated_data.get('members', [])
        if not member_ids:
            message = get_response_message(request, 652)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # (Optional) assert this endpoint is used only for group chats
        # if chat.type != CONSTANTS.CHAT.TYPES.GROUP:
        #     return Response({"detail": "Not a group chat."}, status=400)

        # 2) Parse & validate payload
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_ids = serializer.validated_data.get("members", []) or []
        # Deduplicate while keeping integers
        input_ids = list({int(u) for u in input_ids})

        if not input_ids:
            message = get_response_message(request, 653)
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # 3) Resolve members in this chat
        qs_members = ChatMember.objects.filter(chat_id=chat.id, user_id__in=input_ids).values("user_id", "role")
        existing_map = {row["user_id"]: row["role"] for row in qs_members}
        existing_ids = set(existing_map.keys())

        # Classify outcomes
        skipped_not_members = [uid for uid in input_ids if uid not in existing_ids]
        skipped_self = [uid for uid in input_ids if uid == user_id]  # do not allow self-removal here

        # Protect owners from being removed via this endpoint
        protected_owner_ids = [uid for uid, role in existing_map.items()
                               if role == CONSTANTS.CHAT.ROLES.OWNER]

        # Candidates = existing, minus protected owners, minus requester
        candidates = [uid for uid in existing_ids
                      if uid not in protected_owner_ids and uid != user_id]

        if not candidates:
            # Nothing to remove; return structured OK
            return Response({
                "status": "success",
                "chat_id": chat.id,
                "removed_ids": [],
                "skipped_not_members": skipped_not_members,
                "skipped_protected": protected_owner_ids,
                "skipped_self": skipped_self,
                "requested_count": len(input_ids),
            }, status=status.HTTP_200_OK)

        # 4) Execute deletion atomically
        with transaction.atomic():
            ChatMember.objects.filter(chat_id=chat.id, user_id__in=candidates).delete()

            # 5) After-commit notifications (WebSocket event)
            # def _after_commit():
            # Notify users about the removed members via WebSocket
            # send_socket_about_new_group_chat.apply_async((chat.id, candidates), countdown=1)

            # transaction.on_commit(_after_commit)

        # 6) Structured outcome
        return Response({
            "status": "success",
            "chat_id": chat.id,
            "removed_ids": candidates,
            "skipped_not_members": skipped_not_members,
            "skipped_protected": protected_owner_ids,
            "skipped_self": skipped_self,
            "requested_count": len(input_ids),
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, uid=None, *args, **kwargs):
        q = self.get_queryset().filter(uid=uid, type=CONSTANTS.CHAT.TYPES.GROUP)
        chat = get_object_or_404(q)
        # user_id = get_current_user_id()
        # if not ChatMember.objects.filter(chat=chat, user_id=user_id).exists():
        #     message = get_response_message(request, 650)
        #     return Response(message, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(chat)
        return Response(serializer.data)

    def destroy(self, request, uid=None, *args, **kwargs):
        instance = get_object_or_404(Chat, uid=uid, type=CONSTANTS.CHAT.TYPES.GROUP)
        user_id = get_current_user_id()

        # Ensure the current user is the owner of the chat
        if not ChatMember.objects.filter(chat=instance, user_id=user_id, role=CONSTANTS.CHAT.ROLES.OWNER).exists():
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        # Soft delete the chat
        instance.deleted = True
        instance.deleted_time = timezone.now()
        instance.save()

        # Notify users about the chat deletion via WebSocket
        # send_socket_about_chat_deleted(instance.id, instance.type)
        members = list(ChatMember.objects.filter(chat=instance).values_list('user_id', flat=True))
        send_socket_about_chat_deleted.apply_async((instance.id, instance.type), {'members': members}, countdown=1)

        return Response(status=status.HTTP_204_NO_CONTENT)


class MuteUnmuteChatView(generics.GenericAPIView):
    serializer_class = MuteUnmuteSerializer

    def post(self, request, *args, **kwargs):
        chat_id = kwargs.get('chat_id')
        user_id = get_current_user_id()
        member = ChatMember.objects.filter(chat_id=chat_id, user_id=user_id)
        # Ensure the current user is the member of the chat
        if not member.exists():
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        on_mute = serializer.validated_data.get('on_mute')
        member.update(on_mute=on_mute)

        return Response({'status': 'success'}, status=status.HTTP_200_OK)


class ChatSearchView(views.APIView):
    search = openapi.Parameter('search', openapi.IN_QUERY,
                               description="type anything",
                               type=openapi.TYPE_STRING, required=True)

    response = openapi.Response('response description', SimpleResponseSerializer)

    @swagger_auto_schema(manual_parameters=[search], responses={200: response})
    def get(self, request):
        search = self.request.GET.get('search')
        user_id = get_current_user_id()

        query = """
                SELECT DISTINCT c.id,
                                c.type,
                                CASE
                                    WHEN c.type = 'group' THEN c.title
                                    WHEN c.type = 'private' THEN
                                        CASE
                                            WHEN c.created_by_id = %(user_id)s
                                                THEN CONCAT(u2.last_name, ' ', u2.first_name, ' ', u2.father_name)
                                            ELSE CONCAT(u1.last_name, ' ', u1.first_name, ' ', u1.father_name)
                                            END
                                    ELSE ''
                                    END              AS chat_title,
                                cm_last.text         AS last_message,
                                cm_last.created_date AS last_message_date,
                                c.modified_date,
                                cm_last.type         AS last_message_type,
                                c.uid
                FROM wchat_chat c
                         JOIN wchat_chatmember cm ON c.id = cm.chat_id
                         LEFT JOIN wchat_chatmember cm_other
                                   ON cm_other.chat_id = c.id AND cm_other.user_id != %(user_id)s
                         LEFT JOIN "user_user" u1 ON c.created_by_id = u1.id
                         LEFT JOIN "user_user" u2 ON cm_other.user_id = u2.id
                         LEFT JOIN "wchat_chatmessage" cm_last ON c.last_message_id = cm_last.id
                WHERE cm.user_id = %(user_id)s
                  AND c.deleted = FALSE
                  AND (
                    (c.type = 'group' AND c.title ILIKE %(search_term)s)
                        OR (c.type = 'private' AND
                            (
                                CONCAT(u1.first_name, ' ', u1.last_name) ILIKE %(search_term)s OR
                                CONCAT(u2.first_name, ' ', u2.last_name) ILIKE %(search_term)s OR
                                CONCAT(u1.last_name, ' ', u1.first_name) ILIKE %(search_term)s OR
                                CONCAT(u2.last_name, ' ', u2.first_name) ILIKE %(search_term)s
                                )
                        )
                    )
                ORDER BY c.modified_date DESC; \
                """

        cursor = connection.cursor()
        params = {
            'user_id': user_id,
            'search_term': f'%{search}%'
        }
        cursor.execute(query, params)
        result = cursor.fetchall()
        data = []

        for row in result:
            data.append({
                'id': row[0],
                'type': row[1],
                'chat_title': row[2].strip(),
                'last_message': row[3],
                'last_message_date': row[4],
                'modified_date': row[5],
                'last_message_type': row[6],
                'uid': row[7],
            })

        return Response(data)


def member_of_chat(user_id, chat_id, request):
    if not chat_id:
        message = get_response_message(request, 600)
        message['message'] = message['message'].format(type='chat')
        raise ValidationError2(message)

    if not ChatMember.objects.filter(user_id=user_id, chat_id=chat_id).exists():
        message = get_response_message(request, 651)
        raise ValidationError2(message)
    return True


# class MessageCursorPagination(CursorPagination):
#     page_size = 50
#     page_size_query_param = "page_size"
#     max_page_size = 200
#     ordering = ("-created_date", "-id")
#
#     # (optional) strip start_at_id from generated links so it doesn't linger
#     def get_next_link(self):
#         link = super().get_next_link()
#         if not link: return link
#         return link.replace("&start_at_id=", "&x_start_at_id=").replace("?start_at_id=", "?x_start_at_id=")
#
#     def get_previous_link(self):
#         link = super().get_previous_link()
#         if not link: return link
#         return link.replace("&start_at_id=", "&x_start_at_id=").replace("?start_at_id=", "?x_start_at_id=")


class ChatMessageViewSet(viewsets.ModelViewSet):
    """
    Telegram-fast read path: ha-ha-ha
      - Authorize via membership EXISTS (no Python helper-side query)
      - Cursor pagination on -id (no OFFSET)
      - select_related / prefetch_related to avoid N+1
      - only() to fetch exactly what MessageSerializer uses
      - 'is_read' pre-annotated to avoid per-row queries in get_is_read
    """
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination
    filterset_fields = ['chat']
    ordering_fields = ['created_date', 'id']
    # filter_backends = []
    ordering = ('-created_date', '-id')

    def get_base_queryset(self):
        user_id = get_current_user_id()
        chat_id = self.request.GET.get("chat")

        # SQL-level membership check
        member_q = ChatMember.objects.filter(chat_id=OuterRef("chat_id"), user_id=user_id)

        qs = (
            ChatMessage.objects
            .annotate(is_member=Exists(member_q))
            .filter(is_member=True)
            # relations used by the serializer
            .select_related("sender", "replied_to", "replied_to__sender")
            .prefetch_related(
                Prefetch(
                    "attachments",
                    queryset=ChatMessageFile.objects.only("id", "message_id", "file")),
                Prefetch(
                    "reactions",
                    queryset=ChatMessageReaction.objects.only("id", "message_id", "user_id", "emoji")),
            )
            # pre-annotate is_read to prevent N+1 inside get_is_read()
            .annotate(
                is_read_annotated=Exists(
                    MessageReceiver.objects.filter(message_id=OuterRef("pk"), read__isnull=False)
                )
            )
            # fetch exactly the fields your MessageSerializer touches
            .only(
                "id", "chat_id", "text", "type", "created_date", "edited", "edited_time",
                "sender_id", "replied_to_id",
                "replied_to__id", "replied_to__text", "replied_to__deleted", "replied_to__created_date",
                "replied_to__sender_id",
                "sender__id", "sender__first_name", "sender__last_name",
                "sender__color", "sender__position", "sender__status", "sender__cisco",
                "sender__avatar", "sender__top_level_department", "sender__department",
                "sender__company",
                "replied_to__sender__id",
            )
        )
        if chat_id:
            qs = qs.filter(chat_id=chat_id)

        # DO NOT add order_by here; CursorPagination applies '-id'
        return qs

    def get_queryset(self):
        # Default path (no 'around'): let CursorPagination do the usual thing
        return self.get_base_queryset()

    def list(self, request, *args, **kwargs):
        """
        If `cursor` is present -> default DRF behavior.
        If `around=<message_id>` (and no cursor) -> return a window centered at pivot,
        plus proper previous/next cursor links for bi-directional scrolling.
        """
        paginator = self.paginator
        qs = self.get_base_queryset()

        # If client already paging with cursor, defer to default
        if 'cursor' in request.query_params or 'around' not in request.query_params:
            return super().list(request, *args, **kwargs)

        chat_id = request.query_params.get('chat')
        pivot_id = request.query_params.get('around')
        if not chat_id or not pivot_id:
            return super().list(request, *args, **kwargs)

        try:
            pivot = ChatMessage.objects.only('id', 'chat_id', 'created_date').get(
                id=pivot_id, chat_id=chat_id
            )
        except ChatMessage.DoesNotExist:
            raise ValidationError2({"message": "Pivot message not found in this chat."})

        # Page sizes
        _ctx_above = int(request.query_params.get('ctx_above', 10))
        _ctx_below = int(request.query_params.get('ctx_below', paginator.page_size - _ctx_above))
        ctx_above = min(_ctx_above, paginator.max_page_size)
        ctx_below = min(_ctx_below, paginator.max_page_size)

        # NEWER (nearest above pivot): strict greater-than, ASC (closest first), then reverse to DESC
        newer_near_asc = list(
            qs.filter(
                Q(created_date__gt=pivot.created_date) |
                Q(created_date=pivot.created_date, id__gt=pivot.id)
            ).order_by('created_date', 'id')[:ctx_above]
        )
        newer_near_desc = list(reversed(newer_near_asc))  # keep overall page in DESC

        # OLDER (nearest below pivot): strict less-than, already DESC
        older_near_desc = list(
            qs.filter(
                Q(created_date__lt=pivot.created_date) |
                Q(created_date=pivot.created_date, id__lt=pivot.id)
            ).order_by('-created_date', '-id')[:ctx_below]
        )

        # Initialize paginator context (for link building)
        paginator.request = request
        paginator.base_url = request.build_absolute_uri(request.path)

        # Merge into a single DESC page around the pivot
        items = newer_near_desc + [pivot] + older_near_desc
        data = self.get_serializer(items, many=True).data

        next_link = previous_link = None
        if items:
            head = items[0]  # newest in page (DESC)
            tail = items[-1]  # oldest in page

            # Build real DRF cursor tokens → links
            next_token = paginator.token_for_instance(tail, reverse=False)  # older
            prev_token = paginator.token_for_instance(head, reverse=True)  # newer

            assert not next_token.startswith('http')
            assert not prev_token.startswith('http')

            next_link = paginator.build_link_with_cursor(request, next_token)
            previous_link = paginator.build_link_with_cursor(request, prev_token)

        return Response({
            "count": len(items),
            "next": next_link,  # older (scroll down)
            "previous": previous_link,  # newer (scroll up)
            "anchor_id": int(pivot.id),
            "results": data,
        })

    def update(self, request, pk=None, *args, **kwargs):
        instance = get_object_or_404(ChatMessage, pk=pk)
        current_user_id = get_current_user_id()

        # Check if the current user is the sender
        if instance.sender_id != current_user_id:
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        new_text = request.data.get('text')

        # Update only if the text has changed
        if instance.text != new_text:
            instance.edited = True
            instance.edited_time = timezone.now()

            # Update the message
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            # Schedule update of last message ID in chat
            update_last_message_id_of_chat.apply_async((instance.chat_id,), countdown=1)

            # Notify users about the message update via WebSocket
            send_socket_about_message_update.apply_async((instance.id, instance.chat_id), countdown=1)

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response({'status': 'no_changes'}, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None, *args, **kwargs):
        instance = get_object_or_404(ChatMessage, pk=pk)
        current_user_id = get_current_user_id()

        # Check if the current user is the sender
        if instance.sender_id != current_user_id:
            message = get_response_message(request, 700)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        chat = instance.chat

        with transaction.atomic():
            # Soft delete the message
            instance.deleted = True
            instance.deleted_time = timezone.now()
            instance.save()

            # Update last message ID if needed
            new_last_message = (ChatMessage.objects.filter(chat_id=chat.id).
                                order_by('-created_date').
                                select_related('sender').first())
            new_last_message_id = new_last_message.id if new_last_message else None
            chat.last_message_id = new_last_message_id
            chat.save()

        # Prepare data for socket notification
        socket_data = {
            'last_message_text': new_last_message.text if new_last_message else None,
            'last_message_date': new_last_message.created_date.isoformat() if new_last_message else None,
            'last_message_sender': new_last_message.sender.full_name if new_last_message else None,
        }

        # Notify users about the message deletion via WebSocket
        send_socket_about_message_delete.apply_async((instance.id, instance.type,
                                                      instance.chat_id, chat.type),
                                                     socket_data,
                                                     countdown=1)

        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageSearchView(views.APIView):
    search = openapi.Parameter('search', openapi.IN_QUERY,
                               description="type anything",
                               type=openapi.TYPE_STRING, required=True)

    response = openapi.Response('response description', SimpleResponseSerializer)

    @swagger_auto_schema(manual_parameters=[search], responses={200: response})
    def get(self, request):
        search = self.request.GET.get('search')
        user_id = get_current_user_id()

        query = """
                SELECT cm.id   AS message_id,
                       cm.text AS message_text,
                       cm.type AS message_type,
                       cm.created_date,
                       c.id    AS chat_id,
                       c.type  AS chat_type,
                       COALESCE(
                               CASE
                                   WHEN c.type = 'group' THEN c.title
                                   WHEN c.type = 'private' THEN
                                       CASE
                                           WHEN c.created_by_id = %(user_id)s
                                               THEN u2.last_name || ' ' || u2.first_name
                                           ELSE u1.last_name || ' ' || u1.first_name
                                           END
                                   ELSE 'Unknown'
                                   END, 'Unknown'
                       )       AS chat_title,
                       c.uid
                FROM wchat_chatmessage cm
                         JOIN wchat_chat c ON cm.chat_id = c.id AND c.deleted = false
                         JOIN wchat_chatmember cmem ON cm.chat_id = cmem.chat_id
                         LEFT JOIN "user_user" u1 ON c.created_by_id = u1.id
                         LEFT JOIN wchat_chatmember cm_other
                                   ON cm_other.chat_id = c.id AND cm_other.user_id != %(user_id)s
                         LEFT JOIN "user_user" u2 ON cm_other.user_id = u2.id
                WHERE cm.deleted = FALSE
                  AND cmem.user_id = %(user_id)s
                  AND cm.text ILIKE %(search)s
                ORDER BY cm.created_date DESC; \
                """

        cursor = connection.cursor()
        params = {
            'user_id': user_id,
            'search': f'%{search}%'
        }
        cursor.execute(query, params)
        result = cursor.fetchall()
        data = []

        for row in result:
            data.append({
                'message_id': row[0],
                'message_text': row[1],
                'message_type': row[2],
                'created_date': row[3],
                'chat_id': row[4],
                'chat_type': row[5],
                'chat_title': row[6] if row[6] else 'Unknown',
                'uid': row[7],
            })

        count = len(data)
        return Response({'count': count, 'data': data})


class MessageLinkListView(generics.ListAPIView):
    queryset = ChatMessage.objects.filter(type=CONSTANTS.CHAT.MESSAGE_TYPES.LINK)
    serializer_class = MessageLinkSerializer
    filterset_class = MessageLinkFilter

    def get_queryset(self):
        user_id = get_current_user_id()
        q = super(MessageLinkListView, self).get_queryset().select_related('chat')
        chat_id = self.request.GET.get('chat')

        if member_of_chat(user_id, chat_id, self.request):
            q = q.filter(chat_id=chat_id, chat__deleted=False)
        else:
            q = q.none()

        return q.order_by('-created_date')


class ChatMessageFileListView(generics.ListAPIView):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageFileSerializer
    filterset_class = MessageLinkFilter

    def get_queryset(self):
        user_id = get_current_user_id()
        q = (
            super(ChatMessageFileListView, self)
            .get_queryset()
            .select_related('chat')
            .filter(chat__deleted=False)
            .prefetch_related('attachments')
        )
        chat_id = self.request.GET.get('chat')
        type = self.request.GET.get('type')

        if member_of_chat(user_id, chat_id, self.request):
            q = q.filter(chat_id=chat_id, type=type)
        else:
            q = q.none()

        return q.order_by('-created_date')


class ChatFileCountsView(views.APIView):
    """
    Get the count of files in a chat.
    """

    def get(self, request, *args, **kwargs):
        user_id = get_current_user_id()
        chat_id = kwargs.get('chat_id')

        if not member_of_chat(user_id, chat_id, request):
            message = get_response_message(request, 650)
            return Response(message, status=status.HTTP_403_FORBIDDEN)

        # Group by message file types
        sql = """
              SELECT count(*) AS count, type
              FROM wchat_chatmessage cm
              WHERE chat_id = %(chat_id)s
                AND deleted = false
                AND type in %(type)s
              GROUP BY type \
              """

        params = {
            'chat_id': chat_id,
            'type': CONSTANTS.CHAT.MESSAGE_TYPES.FILES
        }

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        file_counts = {row[1]: row[0] for row in rows}

        return Response(file_counts)


class GetMessagePageView(generics.GenericAPIView):
    """
    Get the page of messages in a chat.
    """
    serializer_class = MessagePageSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat_id = serializer.validated_data.get('chat_id')
        page_size = serializer.validated_data.get('page_size')
        message_id = serializer.validated_data.get('message_id')
        user_id = get_current_user_id()

        # Check if the user is a member of the chat
        member_of_chat(user_id, chat_id, request)

        # Get the target message
        try:
            target_message = ChatMessage.objects.get(id=message_id, chat_id=chat_id)
        except ChatMessage.DoesNotExist:
            raise Http404

        # Get all message ids in the chat
        all_message_ids = list(
            ChatMessage.objects.filter(chat_id=chat_id).
            order_by('-created_date').
            values_list('id', flat=True))

        # Find the index of the target message
        try:
            target_index = all_message_ids.index(target_message.id)
            page = (target_index // page_size) + 1
        except ValueError:
            raise Http404

        return Response({'page': page, 'page_size': page_size})


class GetMessageCursorView(generics.GenericAPIView):
    """
    Returns a cursor URL to open the messages list at the given message_id.
    This replaces the old 'page number' logic.
    """
    serializer_class = MessagePageSerializer

    def post(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)

        chat_id = s.validated_data["chat_id"]
        message_id = s.validated_data["message_id"]
        page_size = s.validated_data.get("page_size")

        # authz: ensure user is a member (your helper)
        member_of_chat(get_current_user_id(), chat_id, request)

        # ensure the message exists in that chat
        ChatMessage.objects.only("id").get(id=message_id, chat_id=chat_id)

        base = request.build_absolute_uri(
            reverse("chat-message-list")
        )
        params = [f"chat={chat_id}", f"start_at_id={message_id}"]
        if page_size:
            params.append(f"page_size={page_size}")
        url = f"{base}?{'&'.join(params)}"

        return Response({"cursor_url": url}, status=status.HTTP_200_OK)
