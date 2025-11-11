from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
    TokenVerifyView,
)

from apps.user import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='users')
router.register(r'user-assistants', views.UserAssistantViewSet, basename='user-assistants')
router.register(r'top-signers', views.TopSignerViewSet, basename='top-signers')
router.register(r'assigned-signers', views.OrdinarySignerViewSet, basename='assigned-signers')
router.register(r'roles', views.RoleViewSet, basename='roles')
router.register(r'project-permissions', views.ProjectPermissionViewSet, basename='project-permissions')
router.register(r'notification-types', views.NotificationTypeViewSet, basename='notification-types')
router.register('birthday-reactions', views.BirthdayReactionViewSet, basename='birthday-reactions')
router.register(r'birthday-comments', views.BirthdayCommentViewSet, basename='birthday-comments')
router.register(r'birthday-congratulations', views.BirthdayCongratulationViewSet, basename='birthday-congratulations')
router.register('mood-reactions', views.MoodReactionViewSet, basename='mood-reactions')
router.register('custom-avatars', views.CustomAvatarViewSet, basename='custom-avatars')
router.register(r'my-selected-contacts', views.MySelectedContactViewSet, basename='my-selected-contacts')

urlpatterns = [
    path('api/v1/user-search/', views.UserGlobalSearchView.as_view(), name='user-search'),
    path('api/v1/send-otp/', views.SendOTPToPhoneView.as_view(), name='send-otp'),
    path('api/v1/verify-phone/', views.VerifyPhoneView.as_view(), name='verify-phone'),
    path('api/v1/login/', views.LoginView.as_view(), name='login'),

    path('api/v1/refresh-token/', TokenRefreshView.as_view(), name='refresh-token'),
    path('api/v1/blacklist-token/', TokenBlacklistView.as_view(), name='blacklist-token'),
    path('api/v1/verify-token/', TokenVerifyView.as_view(), name='verify-token'),
    path('api/v1/user-online/<int:user_id>/', views.IsUserOnlineView.as_view(), name='user-online'),

    path('api/v1/ldap-login/', views.LDAPLogin.as_view(), name='ldap-login'),
    path('api/v1/eds-login/', views.LoginWithEDSView.as_view(), name='eds-login'),
    path('api/v1/profile/', views.ProfileView.as_view(), name='profile'),
    path('api/v1/set-password/', views.NewUserSetPasswordView.as_view(), name='set-password'),
    path('api/v1/change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('api/v1/set-role/<int:pk>/', views.SetRoleToUserView.as_view(), name='set-role'),
    path('api/v1/my-permissions/', views.MyPermissionsView.as_view(), name='my-permissions'),
    path('api/v1/chat-user-search/', views.UserSearchForWChatView.as_view(), name='wchat-search-user'),
    path('api/v1/set-passcode/', views.SetPasscodeView.as_view(), name='set-passcode'),
    path('api/v1/check-passcode/', views.CheckPasscodeView.as_view(), name='check-passcode'),
    path('api/v1/my-salary/', views.MySalaryListView.as_view(), name='my-salary'),
    path('api/v1/my-salary-statistics/', views.AnnualSalaryListView.as_view(), name='annual-salary'),
    path('api/v1/my-equipment/', views.EquipmentView.as_view(), name='my-equipment'),
    path('api/v1/user-birthdays/', views.UserBirthdayView.as_view(), name='user-birthdays'),
    path('api/v1/weekly-activity-percent/', views.WeeklyUserActivityPercentage.as_view(),
         name='weekly-activity-percent'),
    path('api/v1/form-completion-percent/',
         views.FormCompletionPercentage.as_view(),
         name='form-completion-percent'),
    path('api/v1/users-on-vacation/', views.UsersOnVacationView.as_view(), name='users-on-vacation'),
    path('api/v1/user-devices/', views.UserDeviceListCreateView.as_view(), name='user-devices'),
    path('api/v1/', include(router.urls)),
]
