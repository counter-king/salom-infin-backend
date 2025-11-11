import datetime as dt
import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.utils import timezone

from apps.document.models import MINIO_CLIENT, MINIO_BUCKET_NAME


def to_float(v):
    """Coerce Oracle value to Python float; returns None if not numeric."""
    if v is None:
        return None
    if isinstance(v, (float, int)):
        return float(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(',', '.')  # handle "12,34" locales
        try:
            return float(s)
        except ValueError:
            return None
    return None


def fmt_d(d: date) -> str:
    """
    Formats a given date object into a string in the format 'DD.MM.YYYY'.

    Parameters:
    d : date
        The date object to format.

    Returns:
    str
        A string representation of the date in 'DD.MM.YYYY' format.
        E.g., 2023-10-05 becomes '05.10.2023'.
    """
    return d.strftime("%d.%m.%Y")


def fmt_dt(dt: Optional[datetime]) -> str:
    """
    Formats a datetime object into a string in the format "dd.mm.yyyy hh:mm:ss".
    The function uses the server's local timezone or a preferred timezone-aware
    conversion for formatting the datetime.

    Parameters:
        dt (Optional[datetime]): A datetime object to be formatted. If None, an
        empty string is returned.

    Returns:
        str: A formatted datetime string in the specified format or an empty
        string if the input is None.
    """
    if not dt:
        return ""
    # Use server local tz or your preferred tz-aware conversion
    return dt.astimezone().strftime("%d.%m.%Y %H:%M:%S")


def to_py_date(v) -> date | None:
    """
    Converts a value to a Python date object if possible.

    This function takes a value and attempts to convert it to a `date` object.
    It handles various types of inputs including `None`, `date`, `datetime`,
    and string representations of dates in specific formats.
    If the input is `None`, it returns `None`. If the input is already a `date`
    object (but not a `datetime`), it is returned as is. If the input is a `datetime`,
    only the date portion is extracted and returned. For string inputs, it tries to
    parse the date using several common formats. If the input cannot be
    interpreted as a date, a `ValueError` is raised.

    Raises:
        ValueError: If the input value is not recognized as a valid date.

    Args:
        v: The value to be converted to a `date`.

    Returns:
        date | None: A `date` object if the conversion is successful, or `None` if
        the input is `None`.
    """
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        for fmt in ("%d.%m.%Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                pass
    raise ValueError(f"Unrecognized date value: {v!r}")


def build_documents_zip(documents, journal_id, start_date, end_date):
    """
    Create an in-memory zip of all document files from MinIO
    and return an HttpResponse with the zip file.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in documents:
            for doc_file in doc.files.all():
                file_obj = doc_file.file
                if not file_obj:
                    continue

                # resolve object name in minio
                if file_obj.etag:
                    object_name = file_obj.path
                else:
                    if file_obj.year:
                        object_name = f"{file_obj.module}/{file_obj.year}/{file_obj.key}.{file_obj.extension}"
                    else:
                        object_name = f"{file_obj.module}/{file_obj.key}.{file_obj.extension}"

                try:
                    minio_response = MINIO_CLIENT.get_object(MINIO_BUCKET_NAME, object_name)
                    file_bytes = minio_response.read()
                    minio_response.close()
                    minio_response.release_conn()

                    # add to zip with original filename
                    zip_file.writestr(file_obj.name, file_bytes)

                except Exception as e:
                    print(f"Error fetching {file_obj.name}: {e}")

    zip_buffer.seek(0)

    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="documents_journal{journal_id}_{start_date}_to_{end_date}.zip"'
    )
    return response


def to_utc(dt_str: str) -> Optional[dt.datetime]:
    """
    Parse an ISO 8601 datetime string and convert it to a UTC datetime object.
    """
    if not dt_str:
        return None
    s = dt_str.strip().replace(" ", "T")
    # Normalize trailing Z or offsets
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def as_int(x, default=0) -> int:
    try:
        return int(str(x))
    except Exception:
        return default


def as_str(x, default="") -> str:
    try:
        return str(x)
    except Exception:
        return default


def boolish(x) -> bool:
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in ("1", "true", "yes", "y", "on", 1, True)


def to_native_json(data):
    # Safe: DRF ReturnList/ReturnDict -> plain Python JSON-serializable types
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))
