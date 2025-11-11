from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.wchat import views

router = DefaultRouter()
router.register(r'chat/private', views.PrivetChatViewSet, basename='chat-private')
router.register(r'chat/group', views.GroupChatViewSet, basename='chat-group')
router.register(r'chat/messages', views.ChatMessageViewSet, basename='chat-message')
urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/chat/search/', views.ChatSearchView.as_view(), name='chat-search'),
    path('api/v1/chat/mute/<int:chat_id>/', views.MuteUnmuteChatView.as_view(), name='chat-mute'),
    path('api/v1/chat/message/search/', views.MessageSearchView.as_view(), name='message-search'),
    path('api/v1/chat/get-message-page/', views.GetMessagePageView.as_view(), name='get-message-page'),
    path('api/v1/chat/get-message-cursor/', views.GetMessageCursorView.as_view(), name='get-message-page'),
    path('api/v1/chat/message/links/', views.MessageLinkListView.as_view(), name='message-links'),
    path('api/v1/chat/message/files/', views.ChatMessageFileListView.as_view(), name='message-files'),
    path('api/v1/chat/<int:chat_id>/files-count/', views.ChatFileCountsView.as_view(), name='chat-files'),
]
