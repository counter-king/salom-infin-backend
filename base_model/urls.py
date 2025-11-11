from django.urls import path, include

from base_model import views

urlpatterns = [
    path('api/v1/unread-count/', views.UnreadCountViewSet.as_view(), name='inbox-unread-count'),
    path('api/v1/dashboard/users/', views.DashboardUserList.as_view(), name='my-department-users'),
    path('api/v1/dashboard/new-counts/', views.NewCountsView.as_view(), name='new-counts'),
    path('api/v1/dashboard/unread-chat-counts/', views.UnreadChatsCountView.as_view(), name='unread-chats'),
    path('api/v1/dashboard/in-progress-counts/', views.InProgressCountsView.as_view(), name='in-progress-counts'),
    path('api/v1/dashboard/all-counts/', views.AllCountsView.as_view(), name='all-counts'),
    path('api/v1/mock-post', views.MockTestView.as_view(), name='mock-post'),
    path('api/v1/all-urls/', views.ListAllUrlsView.as_view(), name='all-urls'),
]
