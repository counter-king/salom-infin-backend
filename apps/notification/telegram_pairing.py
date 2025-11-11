import datetime
import hashlib
import secrets
import string
import uuid

import jwt
from django.conf import settings
from django.utils import timezone
from jwt import InvalidTokenError, ExpiredSignatureError

PAIRING_TTL_SECONDS = 300  # 3 minutes


def generate_pairing_token(user_id: int) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "nonce": uuid.uuid4().hex,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=PAIRING_TTL_SECONDS),
        "scope": "telegram_pairing"
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token


def generate_short_token(length: int = 32) -> str:
    # raw = secrets.token_bytes(nbytes)
    # return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    ALPHANUM = string.ascii_letters + string.digits
    return ''.join(secrets.choice(ALPHANUM) for _ in range(length))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def compute_expiry():
    return timezone.now() + datetime.timedelta(seconds=PAIRING_TTL_SECONDS)


def validate_pairing_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        return None
    except InvalidTokenError:
        return None

    if payload.get("scope") != "telegram_pairing":
        return None

    return {
        "user_id": int(payload["sub"]),
        "nonce": payload["nonce"],
        "exp": payload["exp"],
    }
