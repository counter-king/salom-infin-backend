import datetime
import os
import re
import unicodedata
from urllib.parse import quote

from django.db import transaction
from django.http import JsonResponse, FileResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views
from rest_framework.decorators import permission_classes, api_view
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.document.helpers import upload_file, _guess_content_type
from apps.document.models import File, MINIO_CLIENT, MINIO_BUCKET_NAME
from apps.document.serializers import FileSerializer

_SAFE_ASCII = re.compile(r"[^A-Za-z0-9._-]+")


@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def upload(request):
    """
    Multi-file upload with:
      - Clean folder structure
      - Safe names
      - SHA-256 integrity
      - Object metadata & tags
    """
    if not request.FILES:
        return JsonResponse({"message": "No files provided"}, status=400)

    module = request.data.get("module", "default").strip()
    duration_ms = request.data.get("duration", None)
    peaks = request.data.get("peaks", None)

    if not module:
        # Preserving your message style
        return JsonResponse({"message": "Field 'module' is required"}, status=400)

    MAX_FILE_MB = 50
    FNAME_LEN_LIMIT = 100

    results = []
    errors = []

    # Use atomic block so either all files are recorded in DB or none
    with transaction.atomic():
        for field_name, dj_file in request.FILES.items():
            original_name = dj_file.name or ""
            content_type = (getattr(dj_file, "content_type", "") or "").lower() or _guess_content_type(original_name)
            file_size_bytes = dj_file.size
            file_size_mb = round(file_size_bytes / 1_000_000, 2)

            if len(original_name) > FNAME_LEN_LIMIT:
                errors.append({
                    "name": original_name,
                    "reason": f"Filename length {len(original_name)} exceeds limit {FNAME_LEN_LIMIT}"
                })
                continue

            # Hard guards
            # if content_type not in ALLOWED_CONTENT_TYPES:
            #     errors.append({
            #         "name": original_name,
            #         "reason": f"Content-Type '{content_type}' is not allowed"
            #     })
            #     continue
            if file_size_mb > MAX_FILE_MB:
                errors.append({
                    "name": original_name,
                    "reason": f"File size {file_size_mb} MB exceeds limit {MAX_FILE_MB} MB"
                })
                continue

            # Upload
            response = upload_file(dj_file, module, original_name)
            object_key = response.get("key")
            key_etag = response.get("key_etag")
            sha256_hex = response.get("sha256")
            etag = response.get("etag")
            version_id = response.get("version_id")
            bucket_name = response.get("bucket")

            year_int = int(object_key.split("/")[1])

            file_obj = File(
                key=object_key,
                name=original_name,
                extension=os.path.splitext(original_name)[1].lower()[1:],  # w/o dot
                size=file_size_bytes,
                module=module,
                year=year_int,
                content_type=content_type,
                path=object_key,
                bucket=bucket_name,
                sha256=sha256_hex,
                etag=etag,
                state="uploaded",
                version_id=version_id,
                peaks=peaks,
                duration=duration_ms,
            )

            file_obj.save()
            results.append(FileSerializer(file_obj).data)

        if errors and not results:
            # All failed -> rollback by raising, or return 400 without saving
            transaction.set_rollback(True)
            return JsonResponse({"message": errors}, status=400)

    # Mixed case: return both successes and errors
    if errors:
        return JsonResponse({"uploaded": results, "message": errors}, status=207, safe=False)

    if len(results) == 1:
        return JsonResponse(results[0], status=201)
    return JsonResponse(results, safe=False, status=200)


# @api_view(['POST'])
# @permission_classes((IsAuthenticated,))
# def upload(request):
#     if request.FILES:
#         data = []
#
#         for uploaded_file in request.FILES.getlist('file'):
#             filename = uploaded_file.name or ''
#             file_size = uploaded_file.size
#             # given_name = request.data.get('name')
#             # check_id = request.data.get('check_id')
#             # type = request.data.get('type')
#             content_type = uploaded_file.content_type.lower()
#             fn, extension = os.path.splitext(filename.lower())
#             is_video = 'video/' in content_type or extension in ('.mp4', '.mpg', '.mpeg', '.avi', '.3gp', '.mov')
#             # is_jpeg = '/jpeg' in content_type or '/jpg' in content_type or extension in ('.jpeg', '.jpg')
#             # is_png = '/png' in content_type or extension == '.png'
#             file_size_mb = round(file_size / (1024 ** 2), 2)
#             uuid_name = uuid4()
#             new_name = "%s.%s" % (uuid_name, filename.split(".")[-1])
#             uploaded_file.name = new_name
#             content = uploaded_file.read()
#
#             doc = File(key=uuid_name,
#                        name=filename,
#                        file=ContentFile(content.read()) if is_video else content,
#                        extension=extension.lower()[1:],
#                        file_size=file_size_mb)
#
#             doc.save()
#             data.append(doc.dict())
#         return JsonResponse(FileSerializer(data, many=True).data, safe=False, status=200)
#     else:
#         return JsonResponse({'message': "Error occurred. Please Retry"}, status=400)


class ServeFileView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def _ascii_fallback(self, filename: str, default="file"):
        """
        Best-effort ASCII fallback that preserves extension.
        """
        name = filename or default
        base, ext = os.path.splitext(name)
        base_norm = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
        base_sanit = _SAFE_ASCII.sub("_", base_norm).strip("._-") or default
        # keep only ASCII in extension; ensure it starts with a dot if present
        ext_sanit = _SAFE_ASCII.sub("", ext)
        if ext_sanit and not ext_sanit.startswith("."):
            ext_sanit = "." + ext_sanit
        return (base_sanit or default) + (ext_sanit or "")

    def _content_disposition(self, original_name: str, fallback_default="download"):
        """
        RFC 6266 + RFC 5987:
        attachment; filename="<ascii>"; filename*=UTF-8''<url-encoded>
        """
        fallback = self._ascii_fallback(original_name, default=fallback_default)
        utf8_encoded = quote(original_name or "", safe="")
        return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{utf8_encoded}'

    file_schema = openapi.Schema(type=openapi.TYPE_STRING, format='binary')

    @swagger_auto_schema(
        operation_description="Download file by id",
        responses={200: openapi.Response('File', file_schema)}
    )
    def get(self, request, *args, **kwargs):
        file_id = kwargs.get('file_id')
        file = get_object_or_404(File, id=file_id)

        try:
            if file.etag:
                object_name = file.path
            else:
                if file.year:
                    object_name = f'{file.module}/{file.year}/{file.key}.{file.extension}'
                else:
                    object_name = f'{file.module}/{file.key}.{file.extension}'

            minio_response = MINIO_CLIENT.get_object(MINIO_BUCKET_NAME, object_name)

            response = FileResponse(minio_response, content_type=file.content_type, as_attachment=False)
            response['Content-Disposition'] = self._content_disposition(file.name)
            response['Cache-Control'] = 'public, max-age=3600'
            return response
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=500)


class ServeFilePresignedUrlView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        file_id = kwargs.get('file_id')
        file = get_object_or_404(File, id=file_id)

        try:
            if file.year:
                object_name = f'{file.module}/{file.year}/{file.key}.{file.extension}'
            else:
                object_name = f'{file.module}/{file.key}.{file.extension}'

            url = MINIO_CLIENT.presigned_get_object(
                MINIO_BUCKET_NAME,
                object_name,
                expires=datetime.timedelta(minutes=15)  # URL valid for 10 minutes
            )
            return JsonResponse({'url': url})
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=500)
