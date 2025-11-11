from django.urls import path, include
from rest_framework import routers

from apps.compose.views.v1.trips import views

router = routers.DefaultRouter()
router.register(r'trips', views.BusinessTripViewSet, basename='trips')
router.register(r'trip-verification', views.TripVerificationViewSet, basename='trip-verification')
router.register(r'trip-places', views.TripPlaceViewSet, basename='trip-places')
router.register(r'set-place', views.SetPlaceToTripViewSet, basename='set-place')
router.register(r'trip-expenses', views.TripExpenseViewSet, basename='trip-expenses')
router.register(r'visited-places', views.VisitedPlaceViewSet, basename='visited-places')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/restore-trip-verification/', views.RestoreTripVerification.as_view(), name='restore-trips'),
    path('api/v1/trips-statistics/by-status/', views.TripsByStatusView.as_view(), name='trips-by-status'),
    path('api/v1/trips-statistics/by-top-departments/', views.TripsByDepartmentView.as_view(),
         name='trips-by-top-departments'),
    path('api/v1/trips-statistics/by-type-line-chart/', views.TripsByTypeLineGraphView.as_view(),
         name='trips-by-type-line-graph'),
    path('api/v1/trips-statistics/by-locations/', views.TripsByLocationsView.as_view(),
         name='trips-by-locations'),
    path('api/v1/trips-statistics/by-route/', views.TripsByRouteView.as_view(), name='trips-by-route'),
    path('api/v1/trips-statistics/by-goals/', views.TripsByTagView.as_view(), name='trips-by-tags'),
    path('api/v1/trips-statistics/by-expense/', views.TripExpenseGraphView.as_view(), name='trips-by-expense'),
    path('api/v1/trip-verifications/<int:business_trip_id>/', views.UpdateTripVerificationsAPIView.as_view(), name='update-trip-verifications'),
    path('api/v1/trip-verification/<int:pk>/reset/', views.ResetTripVerificationAPIView.as_view(), name='reset-trip-verification'),
    path('api/v1/business-trip-certificate-to-pdf/', views.BusinessTripCertificateToPdfView.as_view(), name='business-trip-certificate-to-pdf'),
]
