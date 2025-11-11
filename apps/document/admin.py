from typing import Union

from django.contrib import admin
from apps.document.models import File, MobileApplication


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'get_size', 'created_date', 'created_by')
    search_fields = ('name', 'id')
    autocomplete_fields = ('department',)
    date_hierarchy = 'created_date'
    list_filter = ('module', 'created_date', 'year')
    readonly_fields = (
        'key',
        'content_type',
        'size',
        'file_size',
        'year',
        'path',
        'bucket',
        'sha256',
        'etag',
        'version_id',
        'state',
        'created_date',
        'modified_date',
        'created_by',
        'modified_by',
    )

    def get_size(self, obj) -> str:
        size_bytes: Union[int, None] = getattr(obj, "size", None)

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

    get_size.short_description = 'Size'


@admin.action(description="Delete old file before uploading a new one")
def delete_old_app_file(modeladmin, request, queryset):
    for app in queryset:
        app.delete_old_file()
        app.file = None  # Clear the file field
        app.save()


@admin.register(MobileApplication)
class MobileApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'url', 'created_date')
    search_fields = ('name',)
    date_hierarchy = 'created_date'
    readonly_fields = (
        'created_date',
        'modified_date',
        'created_by',
        'modified_by',
    )
    actions = [delete_old_app_file]
