from django.urls import path, include
from rest_framework import routers

from apps.core import views

router = routers.DefaultRouter()
router.register(r'rate-page', views.RatePageViewSet, basename='rate-page')
router.register(r'managers/branch', views.BranchManagerViewSet, basename='branch-manager')
router.register(r'managers/department', views.DepartmentManagerViewSet, basename='department-manager')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/sql-query/', views.SQLExecuteQueryView.as_view(), name='sql-query'),
    path('api/v1/mobile-verify/', views.EDSMobileVerifyView.as_view(), name='mobile-verify'),
]
