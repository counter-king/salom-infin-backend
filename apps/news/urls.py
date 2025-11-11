from django.urls import path, include
from rest_framework import routers

from apps.news import views

router = routers.DefaultRouter()
router.register('news', views.NewsViewSet, basename='news')
router.register('my-news', views.MyNewsViewSet, basename='my-news')
router.register('moderation-news', views.ModerationNewsViewSet, basename='moderation-news')
router.register('news-moderation-2', views.ModerationNews2ViewSet, basename='news-moderation-2')
router.register('news-categories', views.NewsCategoryViewSet, basename='news-categories')
router.register('news-tags', views.NewsTagViewSet, basename='news-tags')
router.register('news-comments', views.NewsCommentViewSet, basename='news-comments')
router.register('news-likes', views.NewsLikeViewSet, basename='news-likes')
router.register('news-moderation-history', views.NewsModerationHistoryViewSet, basename='news-moderation-history')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
