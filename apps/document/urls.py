from django.urls import path

from apps.document import views

urlpatterns = [
    path('api/v1/upload/', views.upload, name='upload'),
    path('api/v1/file/<int:file_id>/', views.ServeFileView.as_view(), name='serve-file'),
    path(
        'api/v1/file-presigned-url/<int:file_id>/',
        views.ServeFilePresignedUrlView.as_view(),
        name='presigned-url'
    ),
]
