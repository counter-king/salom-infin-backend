import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Optional, List

import requests


@dataclass
class TelegramResult:
    ok: bool
    status: int
    text: Optional[str] = None
    retry_after: Optional[int] = None
    is_blocked: bool = False  # 403
    is_bad_request: bool = False  # 400 (invalid chat, message, etc.)


class TelegramClient:
    def __init__(self, base: str = None, timeout: int = None, session: requests.Session = None):
        self.base = os.getenv('TELEGRAM_BOT_API')
        self.timeout = timeout
        self.s = session or requests.Session()

    def get_headers(self, payload):
        WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
        # Generate signature
        signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature
        }
        return headers

    # def send_message(self, chat_id: int,
    #                  text: str,
    #                  parse_mode: str = "HTML",
    #                  disable_preview: bool = True) -> TelegramResult:
    #     url = f"{self.base}/send-message"
    #     try:
    #         payload = {
    #             "tg_id": chat_id,
    #             "message": text
    #         }
    #         headers = self.get_headers(str(payload))
    #         r = self.s.post(url, json=payload, headers=headers)
    #     except requests.RequestException as e:
    #         # Network error: let caller retry
    #         return TelegramResult(ok=False, status=0, text=str(e))
    #
    #     retry_after = 10
    #     # if r.status_code == 429:
    #     #     # Telegram rate-limit; payload like {"parameters":{"retry_after":N}}
    #     #     try:
    #     #         retry_after = r.json().get("parameters", {}).get("retry_after")
    #     #     except Exception:
    #     #         retry_after = None
    #
    #     is_blocked = r.status_code == 403
    #     is_bad = r.status_code == 400
    #
    #     ok = (200 <= r.status_code < 300)
    #     msg = None
    #     try:
    #         body = r.json()
    #         msg = body.get("description")
    #     except Exception:
    #         msg = r.text[:500]
    #
    #     return TelegramResult(
    #         ok=ok, status=r.status_code, text=msg,
    #         retry_after=retry_after,
    #         is_blocked=is_blocked, is_bad_request=is_bad
    #     )

    def send_message(
            self,
            payload: dict,
            *,
            timeout: int = 15,
            parse_mode: str = "HTML",
            disable_preview: bool = True
    ) -> List[dict]:
        """
        Send a pre-built payload to your gateway.
        - payload may be single: {"tg_id": ..., "message": ..., ...}
          or batch: {"messages": [ {...}, {...} ]}
        Returns: list of results (len=1 for single; len=N for batch), each:
          {"ok": bool, "status": int, "text": str|None, "retry_after": int|None,
           "is_blocked": bool, "is_bad_request": bool}
        """
        s = self.s

        # Determine how many items we expect in the response mapping
        count = len(payload.get("messages", [])) if "messages" in payload else 1

        # Canonical JSON for stable signing
        # body = json.dumps(payload)
        headers = self.get_headers(str(payload))

        url = f"{self.base}/send-message"
        try:
            r = s.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            return [{"ok": False, "status": 0, "text": str(e),
                     "retry_after": None, "is_blocked": False,
                     "is_bad_request": False} for _ in range(count)]

        retry_after = None
        if r.status_code == 429:
            try:
                retry_after = r.json().get("parameters", {}).get("retry_after")
            except Exception:
                retry_after = None

        try:
            body_json = r.json()
            print(body_json)
            text_msg = body_json.get("description") or body_json.get("message") or r.reason
        except Exception:
            body_json, text_msg = None, (r.text or "")[:500]

        # Per-item results if server provides them; else broadcast the same result
        results = []
        per_item = body_json.get("results") if isinstance(body_json, dict) else None
        if isinstance(per_item, list) and per_item:
            for item in per_item:
                st_code = r.status_code
                results.append({
                    "ok": bool(item.get("ok", 200 <= st_code < 300)),
                    "status": st_code,
                    "text": item.get("description") or item.get("message") or text_msg,
                    "retry_after": retry_after,
                    "is_blocked": (st_code == 403),
                    "is_bad_request": (st_code == 400),
                })
            while len(results) < count:  # pad if server returned fewer than sent
                results.append({
                    "ok": 200 <= r.status_code < 300,
                    "status": r.status_code,
                    "text": text_msg,
                    "retry_after": retry_after,
                    "is_blocked": (r.status_code == 403),
                    "is_bad_request": (r.status_code == 400),
                })
        else:
            ok = 200 <= r.status_code < 300
            results = [{
                "ok": ok,
                "status": r.status_code,
                "text": text_msg,
                "retry_after": retry_after,
                "is_blocked": (r.status_code == 403),
                "is_bad_request": (r.status_code == 400),
            } for _ in range(count)]

        return results

    def send_user_status(self, chat_id: int,
                         code: str) -> TelegramResult:
        url = f"{self.base}/send-pair-status"
        try:
            payload = {
                "tg_id": chat_id,
                "status": code
            }
            headers = self.get_headers(str(payload))
            r = self.s.post(url, json=payload, headers=headers)
        except requests.RequestException as e:
            # Network error: let caller retry
            return TelegramResult(ok=False, status=0, text=str(e))

        retry_after = 10

        is_blocked = r.status_code == 403
        is_bad = r.status_code == 400

        ok = (200 <= r.status_code < 300)
        msg = None
        try:
            body = r.json()
            msg = body.get("description")
        except Exception:
            msg = r.text[:500]

        return TelegramResult(
            ok=ok, status=r.status_code, text=msg,
            retry_after=retry_after, is_blocked=is_blocked,
            is_bad_request=is_bad
        )
