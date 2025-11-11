"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from config import api_secret
from config.schema_generators import BothHttpAndHttpsSchemaGenerator

public_schema_view = get_schema_view(
    openapi.Info(
        title="Digital Workspace API",
        default_version='v1',
        description="This is a documentation for Digital Workspace API",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    urlconf='config.public_urls'
)

schema_view = get_schema_view(
    openapi.Info(
        title="Digital Workspace API",
        default_version='v1',
        description="This is a documentation for Digital Workspace API",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    generator_class=BothHttpAndHttpsSchemaGenerator,
    urlconf='config.private_urls'
)

urlpatterns = [
    # public urls and swagger doc
    path('', include('config.public_urls')),
    path(f'public/swagger/{api_secret.API_PUBLIC_UUID}/', public_schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui-pub'),
    path(f'public/redoc/{api_secret.API_PUBLIC_UUID}/', public_schema_view.with_ui('redoc', cache_timeout=0),
         name='schema-redoc-pub'),

    # swagger & docs
    path(f'swagger/{api_secret.API_SECRET_UUID}/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),
    path(f'redoc/{api_secret.API_SECRET_UUID}/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # local apps
    path('', include('config.private_urls')),
]

if settings.DEBUG:
    # urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
