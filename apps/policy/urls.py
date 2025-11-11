from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.policy.views import (
    ResourceViewSet,
    ActionViewSet,
    RoleViewSet,
    PolicyViewSet,
    RoleAssignmentViewSet,
    MePoliciesViewSet,
    MeResourcesViewSet,
)

router = DefaultRouter()
router.register(r"resources", ResourceViewSet, basename="ac-resources")
router.register(r"actions", ActionViewSet, basename="ac-actions")
router.register(r"roles", RoleViewSet, basename="ac-roles")
router.register(r"", PolicyViewSet, basename="ac-policies")
router.register(r"role/assignments", RoleAssignmentViewSet, basename="ac-assignments")
router.register(r"me/polices", MePoliciesViewSet, basename="me-policies")
router.register(r"me/resources", MeResourcesViewSet, basename="me-resources")
urlpatterns = [
    path("api/v1/policies/", include(router.urls)),
    # path("check/", check_permission, name="ac-check-permission"),
    # path("compose/scope/<int:user_id>/", compose_list_scope, name="ac-compose-scope"),
]
