from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.notification import views

urlpatterns = [
    path('api/v1/telegram/request/', views.CreateTelegramPairRequestView.as_view(), name='telegram-request'),
    path('api/v1/telegram/bot-callback/', views.TelegramBotCallbackView.as_view(), name='telegram-bot-callback'),
    path('api/v1/telegram/confirm/', views.ConfirmTelegramPairingView.as_view(), name='telegram-confirm'),
    path('api/v1/telegram/unlink/', views.UnlinkTelegramProfileView.as_view(), name='telegram-unlink'),
    path('api/v1/telegram/profiles/', views.TelegramProfilesView.as_view(), name='telegram-profiles'),
    path('api/v1/telegram/send-test-message/', views.SendTestMessageView.as_view(), name='telegram-send-message'),
]
