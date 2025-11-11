from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.company import views

router = DefaultRouter()
router.register(r'companies', views.CompanyViewSet, basename='companies')
router.register(r'positions', views.PositionViewSet, basename='positions')
router.register(r'departments', views.DepartmentViewSet, basename='departments')
router.register(r'departments-with-users', views.DepartmentWithUsersViewSet, basename='departments-with-users')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
