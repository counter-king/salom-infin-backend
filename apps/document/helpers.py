import base64
import datetime
import hashlib
import mimetypes
import os
import re
import tempfile
from uuid import uuid4

from minio import Minio
from minio.commonconfig import Tags
from minio.error import S3Error

# ---------- MinIO client (env-driven, ready for prod) ----------
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.getenv("MINIO_BUCKET_NAME", "app-prod-docs")

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
    "audio/mpeg",
    "video/mp4",
    "audio/m4a",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/gzip",
}

# ---------- Helpers ----------
SAFE = re.compile(r"[^a-z0-9._-]")


def _sanitize_component(value: str) -> str:
    v = (value or "").strip().lower()
    v = SAFE.sub("-", v)
    v = re.sub(r"-{2,}", "-", v)
    return v.strip("-") or "general"


def _split_base_ext(filename: str):
    base, ext = os.path.splitext(filename)
    return _sanitize_component(base), ext.lower()


def _guess_content_type(filename: str, default="application/octet-stream") -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or default


def _ensure_bucket(bucket: str):
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error as e:
        if e.code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise


def _hash_and_prepare_stream(file_obj) -> tuple:
    """
    Returns (stream, total_size_int, sha256_hex).
    Works for Django InMemoryUploadedFile / TemporaryUploadedFile / any file-like.
    """
    sha256 = hashlib.sha256()
    try:
        # If seekable, hash in-place and rewind
        pos0 = file_obj.tell()
        file_obj.seek(0)
        total = 0
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
            total += len(chunk)
        file_obj.seek(0)
        return file_obj, total, sha256.hexdigest()
    except Exception:
        # Not seekable -> spool to temp
        spooled = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
        total = 0
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
            spooled.write(chunk)
            total += len(chunk)
        spooled.seek(0)
        return spooled, total, sha256.hexdigest()


def _build_object_key(module: str, original_name: str) -> str:
    """
    Folder structure:
      uploads/YYYY/MM/DD/<module>/<slug>-<uuid>.<ext>
    """
    now = datetime.datetime.utcnow()
    yyyy = now.strftime("%Y")
    mm = now.strftime("%m")
    dd = now.strftime("%d")

    module_clean = _sanitize_component(module)
    _, ext = _split_base_ext(original_name or "file")
    if not ext:
        inferred = _guess_content_type(original_name)
        guessed_ext = mimetypes.guess_extension(inferred or "") or ""
        ext = guessed_ext or ""

    final_name = f"{uuid4().hex}{ext}"
    return f"uploads/{yyyy}/{mm}/{dd}/{module_clean}/{final_name}"


def _put_object(bucket: str, object_name: str,
                stream, size_bytes: int,
                content_type: str, meta: dict, tags):
    tags_for_object = Tags(for_object=True)
    for k, v in (tags or {}).items():
        tags_for_object[k] = v

    return client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=stream,
        length=size_bytes,
        content_type=content_type,
        metadata=meta,
        tags=tags_for_object,
    )


# ---------- If you prefer to call upload_file directly elsewhere ----------
def upload_file(file_obj, module: str, original_name: str) -> dict:
    """
    Helper for single-file flows; returns the same dict shape you persist.
    """
    _ensure_bucket(MINIO_BUCKET)

    content_type = (getattr(file_obj, "content_type", "") or "").lower() or _guess_content_type(original_name)
    object_key = _build_object_key(module, original_name)
    stream, size_bytes, sha256_hex = _hash_and_prepare_stream(file_obj)

    now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    name_b64 = base64.b64encode((original_name or "").encode("utf-8")).decode("ascii")

    meta = {
        "original-name": name_b64,
        "sha256": sha256_hex,
        "uploaded-at-utc": now_utc,
        "module": _sanitize_component(module),
    }
    tags_map = {
        "module": _sanitize_component(module),
        "state": "uploads",
        "y": object_key.split("/")[1],
        "m": object_key.split("/")[2],
        "d": object_key.split("/")[3],
    }
    tags = Tags(for_object=True)
    for k, v in tags_map.items():
        tags[k] = v

    try:
        put_res = _put_object(
            bucket=MINIO_BUCKET,
            object_name=object_key,
            stream=stream,
            size_bytes=size_bytes,
            content_type=content_type,
            meta=meta,
            tags=tags,
        )
    finally:
        try:
            if stream is not file_obj and hasattr(stream, "close"):
                stream.close()
        except Exception:
            pass

    return {
        "bucket": MINIO_BUCKET,
        "key_etag": str(put_res.etag) if hasattr(put_res, "etag") else str(uuid4()),
        "key": object_key,
        "etag": getattr(put_res, "etag", None),
        "version_id": getattr(put_res, "version_id", None),
        "size_bytes": size_bytes,
        "content_type": content_type,
        "sha256": sha256_hex,
    }
