from django.urls import path, include
from rest_framework import routers

from apps.compose.views.v1.negotiation import views

router = routers.DefaultRouter()
router.register(r'negotiation-types', views.NegotiationTypeViewSet, basename='negotiation-types')
router.register(r'negotiation-sub-types', views.NegotiationSubTypeViewSet, basename='negotiation-sub-types')
router.register(r'negotiation', views.NegotiationViewSet, basename='negotiation')
router.register(r'negotiation-instances', views.NegotiationInstanceViewSet, basename='negotiation-instances')
router.register(r'negotiators', views.NegotiatorViewSet, basename='negotiators')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
