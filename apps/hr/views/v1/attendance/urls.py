from django.urls import path, include
from rest_framework import routers

from apps.hr.views.v1 import attendance as aviews

router = routers.DefaultRouter()
router.register(r'attendance', aviews.AttendanceViewSet, basename='attendance')
router.register(r'my-attendance', aviews.MyAttendanceViewSet, basename='my-attendance')
router.register(r'work-schedules', aviews.WorkScheduleViewSet, basename='work-schedule')
router.register(r"employee-schedules", aviews.EmployeeScheduleViewSet, basename='employee-schedule')
router.register(r'hr/branch-scopes', aviews.HRBranchScopeViewSet, basename='hr-branch-scope')
router.register(r'hr/department-scopes', aviews.HRDepartmentScopeViewSet, basename='hr-department-scope')
router.register(r'hr/assigned-users', aviews.AssignedHrUsersView, basename='hr-assigned-scoped-user')
router.register(r'attendance-exceptions', aviews.AttendanceExceptionViewSet, basename='attendance-exception')

urlpatterns = [
    path('api/v1/attendance/summary/', aviews.AttendanceSummaryTotals.as_view(), name='attendance-summary'),
    path('api/v1/', include(router.urls)),
]
