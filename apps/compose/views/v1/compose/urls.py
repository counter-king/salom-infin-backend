from django.urls import path, include
from rest_framework import routers

from apps.compose.views.v1.compose import views

router = routers.DefaultRouter()
router.register(r'compose/(?P<company>[\w-]+)', views.ComposeViewSet, basename='compose')
router.register(r'compose-list/(?P<company>[\w-]+)', views.ComposeListViewSet, basename='compose-list')
router.register(r'approvers', views.ApproveViewSet, basename='approvers')
router.register(r'signers', views.SignerViewSet, basename='signers')
router.register(r'tags', views.TagViewSet, basename='tags')
router.register(r'iabs/actions', views.IABSActionHistoryViewSet, basename='iabs-actions')
router.register(r'iabs/request-calls', views.IABSRequestCallHistoryViewSet, basename='iabs-request-calls')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/restore-compose/<int:compose_id>/', views.RestoreCompose.as_view(), name='restore-compose'),
]
