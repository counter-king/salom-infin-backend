import hashlib
import json
import random
from typing import List, Any, Dict, Optional

from celery import shared_task
from django.utils import timezone

from .models import TelegramProfile, TelegramNotificationLog
from .telegram_client import TelegramClient
from .template_loader import render_notification


def make_idempotency_key(user_id: int, template: str, context: dict) -> str:
    payload = {"u": user_id, "t": template, "c": context}
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()


def _next_backoff(attempt: int) -> int:
    # exponential backoff with full jitter, capped
    base = min(2 ** attempt, 64)  # seconds
    return random.randint(1, base)


@shared_task(bind=True, max_retries=0)  # retries handled manually (429)
def send_telegram_notification(self,
                               user_ids: List[int],
                               message_type: str,
                               template_key: str,
                               context: Dict[str, Any],
                               idem_key: Optional[str] = None):
    """
    Batch send with per-user idempotency, proper 403/400 handling, and 429 retry-after.
    Input:
      - user_ids: list[int]
      - template_key: str
      - context: dict
    """

    if not user_ids:
        return {"status": "empty_input"}

    client = TelegramClient()

    # 1) Prepare per-user logs and messages
    messages: List[Dict[str, Any]] = []
    idx_to_user: List[int] = []  # maps message index -> user_id
    per_user_logs: Dict[int, TelegramNotificationLog] = {}
    no_chat_users: List[int] = []

    for i, uid in enumerate(user_ids):
        key = idem_key or make_idempotency_key(uid, template_key, context)

        log, created = TelegramNotificationLog.objects.get_or_create(
            key=key,
            defaults={
                "user_id": uid,
                "chat_id": 0,
                "template": template_key,
                "payload": {"context": context},
                "status": "pending",
            },
        )
        per_user_logs[uid] = log

        # If already sent, skip generating a message
        # if (not created) and log.status == "sent":
        #     continue

        # Resolve active chat
        try:
            tp = TelegramProfile.objects.get(user_id=uid, is_active=True)
        except TelegramProfile.DoesNotExist:
            log.status = "failed"
            log.error = "No active chat_id"
            log.attempts += 1
            log.save(update_fields=["status", "error", "attempts"])
            no_chat_users.append(uid)
            continue

        # per-user context (handles list or dict)
        per_ctx = context[i] if isinstance(context, list) and i < len(context) else (context or {})

        # Render per-user text (language-aware if you have it)
        text = render_notification(template_key, per_ctx, getattr(tp, "language", None))

        # Stash for later update even before send result
        log.chat_id = tp.chat_id
        log.attempts += 1
        log.payload = {"context": context, "text": text}
        log.save(update_fields=["chat_id", "attempts", "payload"])

        messages.append({
            "tg_id": tp.chat_id,
            "message": text,
            "type": message_type,
            # keep optional fields if your gateway uses them
            # "type": "notification",
            # "additional_data": {"priority": "high"},
        })
        idx_to_user.append(uid)

    # If nothing to send (all already sent or no-chat), return summary
    # if not messages:
    #     return {
    #         "status": "nothing_to_send",
    #         "already_sent": [uid for uid, lg in per_user_logs.items() if lg.status == "sent"],
    #         "no_chat": no_chat_users,
    #     }

    # 2) Send in one batch
    payload = {"messages": messages}
    results = client.send_message(payload)  # returns list aligned to 'messages'

    # 3) Apply per-item outcomes
    to_retry: List[int] = []
    for i, res in enumerate(results):
        uid = idx_to_user[i]
        log = per_user_logs[uid]

        # update common fields
        log.error = res.get("text")
        log.save(update_fields=["error"])

        if res.get("ok"):
            log.status = "sent"
            log.sent_at = timezone.now()
            log.save(update_fields=["status", "sent_at"])
            continue

        status = int(res.get("status", 0))
        is_blocked = bool(res.get("is_blocked"))
        is_bad = bool(res.get("is_bad_request"))

        if is_blocked:  # 403
            TelegramProfile.objects.filter(user_id=uid, is_active=True).update(is_active=False)
            log.status = "failed"
            log.save(update_fields=["status"])
            continue

        if is_bad:  # 400
            log.status = "failed"
            log.save(update_fields=["status"])
            continue

        # 429 → schedule per-user retry (only those affected)
        if status == 429:
            ra = res.get("retry_after")
            if ra is not None:
                to_retry.append(uid)
                countdown = int(ra) + random.randint(0, 2)
                # schedule a minimal batch containing only this user
                send_telegram_notification.apply_async(
                    args=([uid], message_type, template_key, context, idem_key),
                    countdown=countdown,
                )
                continue

        # default: fail
        log.status = "failed"
        log.save(update_fields=["status"])

    # 4) Summary
    sent = [uid for uid, lg in per_user_logs.items() if lg.status == "sent"]
    failed = [uid for uid, lg in per_user_logs.items() if lg.status == "failed"]

    return {
        "status": "done",
        "sent": sent,
        "failed": failed,
        "no_chat": no_chat_users,
        "retry_scheduled_for": to_retry,
    }

# @shared_task(bind=True, max_retries=0)  # we manage retries manually to honor retry_after
# def send_telegram_notification(self,
#                                user_id: int,
#                                template_key: str,
#                                context: dict,
#                                idem_key: str = None):
#     """
#     Robust send with:
#     - idempotency
#     - 429 retry_after handling
#     - exponential backoff + jitter
#     - disable chat on 403
#     """
#     client = TelegramClient()
#     key = idem_key or make_idempotency_key(user_id, template_key, context)
#
#     # Get or create log row (idempotent)
#     log, created = TelegramNotificationLog.objects.get_or_create(
#         key=key,
#         defaults={
#             "user_id": user_id,
#             "chat_id": 0,
#             "template": template_key,
#             "payload": {"context": context},
#             "status": "pending",
#         },
#     )
#     if not created and log.status == "sent":
#         return {"status": "already_sent", "key": key}
#
#     # Resolve chat_id
#     try:
#         tp = TelegramProfile.objects.get(user_id=user_id, is_active=True)
#     except TelegramProfile.DoesNotExist:
#         log.status = "failed"
#         log.error = "No active chat_id"
#         log.attempts += 1
#         log.save(update_fields=["status", "error", "attempts"])
#         return {"status": "no_chat", "key": key}
#
#     text = render_notification(template_key, context, tp.language)
#     result = client.send_message(tp.chat_id, text)
#
#     # update log common fields
#     log.chat_id = tp.chat_id
#     log.attempts += 1
#     log.payload = {"context": context, "text": text}
#     log.error = result.text
#     log.save(update_fields=["chat_id", "attempts", "payload", "error"])
#
#     # Handle outcomes
#     if result.ok:
#         log.status = "sent"
#         log.sent_at = timezone.now()
#         log.save(update_fields=["status", "sent_at"])
#         return {"status": "sent", "key": key}
#
#     # 403 → user blocked bot, deactivate profile (don’t hammer)
#     if result.is_blocked:
#         TelegramProfile.objects.filter(pk=tp.pk).update(is_active=False)
#         log.status = "failed"
#         log.save(update_fields=["status"])
#         return {"status": "blocked", "key": key, "error": result.text}
#
#     # 400 → non-retryable (bad request / invalid chat / invalid message)
#     if result.is_bad_request:
#         log.status = "failed"
#         log.save(update_fields=["status"])
#         return {"status": "bad_request", "key": key, "error": result.text}
#
#     # 429 → honor retry_after if present
#     if result.status == 429 and result.retry_after:
#         countdown = int(result.retry_after) + random.randint(0, 2)
#         send_telegram_notification.apply_async(
#             args=(user_id, template_key, context, key),
#             countdown=countdown,
#         )
#         return {"status": "retry_scheduled", "after": countdown}
#
#     # give up
#     log.status = "failed"
#     log.save(update_fields=["status"])
#     return {"status": "failed", "key": key, "error": result.text}
