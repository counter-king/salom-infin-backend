from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.wcalendar import views

router = DefaultRouter()
router.register(r'calendar', views.CalendarModelViewSet, basename='calendar')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
