from django.urls import path, include
from rest_framework import routers

from apps.hr.views.v1 import payrolls as payrolls_views

router = routers.DefaultRouter()

router.register(r"payroll/periods", payrolls_views.PayrollPeriodViewSet, basename="payroll-period")

urlpatterns = [
    path("api/v1/", include(router.urls)),
    path(
        "api/v1/payrolls/summary/",
        payrolls_views.PayrollSummaryView.as_view(),
        name="payroll-summary",
    ),
    path(
        "api/v1/payrolls/comparison/",
        payrolls_views.PayrollComparisonView.as_view(),
        name="payroll-comparison",
    ),
    path(
        "api/v1/payrolls/by-company-type/",
        payrolls_views.PayrollByDepartmentView.as_view(),
        name="payroll-by-departments",
    ),
]
