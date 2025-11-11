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
from django.contrib import admin
from django.urls import path, include

from config import api_secret

urlpatterns = [
    # django admin
    path(f'admin/{api_secret.API_SECRET_UUID}/', admin.site.urls),

    # local apps
    path('', include('apps.reference.urls')),
    path('', include('apps.user.urls')),
    path('', include('apps.docflow.urls')),
    path('', include('apps.company.urls')),
    path('', include('apps.compose.urls')),
    path('', include('apps.document.urls')),
    path('', include('apps.wcalendar.urls')),
    path('', include('apps.wchat.urls')),
    path('', include('apps.news.urls')),
    path('', include('base_model.urls')),
    path('', include('apps.core.urls')),
    path('', include('apps.hr.urls')),
    path('', include('apps.policy.urls')),
    path('', include('apps.notification.urls')),
]
