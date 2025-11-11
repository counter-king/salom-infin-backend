import os

from django.conf import settings
from django.db import models
from minio import Minio

from base_model.models import BaseModel
from config.storage import CustomSFTPStorage
from utils.constants import CONSTANTS

FILE_URL = os.getenv('STORAGE_URL')
host = os.getenv('STORAGE_HOST')
user = os.getenv('SFTP_USER')
password = os.getenv('SFTP_PASSWORD')
SFTP = CustomSFTPStorage()

# MinIO client setup
MINIO_CLIENT = Minio(
    endpoint=os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=False  # Set to True if you're using HTTPS
)

MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME')
FILES_ROOT = os.path.join(settings.BASE_DIR, '..', 'files')


class File(BaseModel):
    key = models.CharField(max_length=500, null=True, blank=True, unique=True)
    file = models.FileField(storage=SFTP, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    department = models.ForeignKey("company.Department", on_delete=models.SET_NULL, null=True, blank=True)
    extension = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.FloatField(null=True, blank=True)
    size = models.BigIntegerField(null=True, blank=True, help_text='Size in bytes')
    module = models.CharField(max_length=100, null=True, blank=True)
    year = models.CharField(max_length=4, null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    path = models.CharField(max_length=255, null=True, blank=True)
    bucket = models.CharField(max_length=128, default="app-prod-docs", db_index=True, null=True)
    sha256 = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    etag = models.CharField(max_length=64, null=True, blank=True)
    version_id = models.CharField(max_length=128, null=True, blank=True)
    state = models.CharField(max_length=32, default="uploaded", db_index=True, null=True)
    duration = models.IntegerField(null=True, blank=True,
                                   help_text='Duration in seconds. If file is audio or video or voice.')
    peaks = models.JSONField(default=list, blank=True, null=True,
                             help_text='Audio peaks data. If file is audio or voice.')

    def __str__(self):
        return f'{self.name}'

    class Meta:
        indexes = [
            models.Index(fields=['key', 'name', 'extension'])
        ]

    @property
    def url(self):
        if self.file and hasattr(self.file, 'url'):
            return FILE_URL + self.file.url
        return None

    @property
    def size_(self) -> str:
        size_bytes = self.size

        if not size_bytes:
            return "0 B"

        # SI units (powers of 1000): B, KB, MB, GB, TB, PB
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(size_bytes)
        i = 0
        while size >= 1000.0 and i < len(units) - 1:
            size /= 1000.0
            i += 1
        if i == 0:
            return f"{int(size)} {units[i]}"
        return f"{size:.2f} {units[i]}"

    def dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'created_date': str(self.created_date),
            'file_size': self.file_size,
            'size': self.size,
            'extension': self.extension
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'created_date': self.created_date,
            'file_size': self.file_size,
            'size': self.size,
            'extension': self.extension
        }


class MobileApplication(BaseModel):
    file = models.FileField(upload_to='apps/', null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=50, unique=True, choices=CONSTANTS.APP_TYPES.CHOICES)

    def __str__(self):
        return f'{self.name}'

    @property
    def url(self):
        if self.file and hasattr(self.file, 'url'):
            return FILE_URL + self.file.url
        return None

    @property
    def path(self):
        if self.file and hasattr(self.file, 'path'):
            return self.file.path
        return None

    def delete_old_file(self):
        if self.file:
            # Build full path to files/apps/filename.apk
            relative_path = self.file.name  # example: apps/filename.apk
            full_path = os.path.join(FILES_ROOT, relative_path)  # This becomes files/apps/filename.apk
            if os.path.exists(full_path):
                os.remove(full_path)
