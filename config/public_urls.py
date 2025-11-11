from django.urls import path, include

from apps.user.views import LoginView

urlpatterns = [
    path('login', LoginView.as_view()),
]
