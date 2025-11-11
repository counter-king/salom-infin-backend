from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.news.filters import NewsFilter
from apps.news.models import (
    News,
    NewsCategory,
    NewsTag,
    NewsComment,
    NewsLike,
    NewsModerationHistory,
)
from apps.news.serializers import (
    NewsSerializer,
    NewsCategorySerializer,
    NewsTagSerializer,
    NewsCommentSerializer,
    NewsLikeSerializer,
    NewsApprovalSerializer,
    NewsModerationHistorySerializer,
)
from apps.news.tasks import update_news_view_count
from apps.policy.permissions import HasDynamicPermission
from apps.policy.scopes.registry import get_strategy
from utils.constants import CONSTANTS
from utils.exception import get_response_message


class NewsTagViewSet(viewsets.ModelViewSet):
    queryset = NewsTag.objects.all()
    serializer_class = NewsTagSerializer
    search_fields = ['name', ]
    filterset_fields = ['categories']


class NewsCategoryViewSet(viewsets.ModelViewSet):
    queryset = NewsCategory.objects.all()
    serializer_class = NewsCategorySerializer


class NewsViewSet(viewsets.GenericViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = News.objects.order_by('-published_date', '-created_date')
    serializer_class = NewsSerializer
    filterset_class = NewsFilter
    ordering = ['-published_date', 'like_counts', 'view_counts', 'created_date']
    search_fields = ['title', 'description', 'contents__content']

    def get_queryset(self):
        return (News.objects.select_related('category', 'created_by').
                prefetch_related('tags', 'contents', 'comments').
                filter(status=CONSTANTS.NEWS_STATUS.PUBLISHED))

    # acton for approve news

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        update_news_view_count.delay(instance.id, request.user.id)
        return super().retrieve(request, *args, **kwargs)

    @action(methods=['get'], detail=False, url_path='unread-count', url_name='unread-count')
    def unread_count(self, request, *args, **kwargs):
        user_id = request.user.id
        unread_news_count = News.objects.filter(status=CONSTANTS.NEWS_STATUS.PUBLISHED).filter(
            ~Q(viewers__viewer_id=user_id)
        ).count()

        return Response({'count': unread_news_count})


class MyNewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer
    filterset_class = NewsFilter
    ordering = ['like_counts', 'view_counts', 'created_date']
    search_fields = ['title', 'description', 'contents__content']

    def get_queryset(self):
        return (News.objects.
                select_related('category', 'created_by').
                prefetch_related('tags', 'contents', 'comments').
                filter(created_by=self.request.user).order_by('-modified_date'))

    def perform_update(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        if instance.created_by != user:
            message = get_response_message(request, 700)
            return Response(message, status=403)

        return super().update(request, *args, **kwargs)


class ModerationNewsViewSet(viewsets.GenericViewSet,
                            mixins.ListModelMixin,
                            mixins.RetrieveModelMixin):
    queryset = News.objects.none()
    serializer_class = NewsSerializer
    filterset_class = NewsFilter
    search_fields = ['title', 'description', 'contents__content']

    def get_queryset(self):
        user = self.request.user
        if user.roles.filter(name='moderator').exists():
            return (News.objects
                    .select_related('category', 'created_by')
                    .prefetch_related('tags', 'contents', 'comments')
                    .annotate(status_priority=News.get_status_ordering())
                    .order_by('status_priority', '-modified_date'))
        return News.objects.none()

    @action(methods=['put'],
            detail=True,
            url_path='approve',
            serializer_class=NewsApprovalSerializer)
    def approve(self, request, pk=None, *args, **kwargs):
        user = request.user
        if not user.roles.filter(name='moderator').exists():
            message = get_response_message(request, 700)
            return Response(message, status=403)

        instance = get_object_or_404(News, pk=pk)
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.status = serializer.validated_data.get('status')
        instance.cancelled_reason = serializer.validated_data.get('cancelled_reason', None)
        instance.published_date = timezone.now()
        instance.save()
        return Response(serializer.data)

    @action(methods=['get'], detail=False, url_path='count', url_name='count')
    def count(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response({'count': queryset.count()})


# =================== Testing role based access control ===================#
class ModerationNews2ViewSet(mixins.ListModelMixin,
                             mixins.RetrieveModelMixin,
                             viewsets.GenericViewSet):
    serializer_class = NewsSerializer
    filterset_class = NewsFilter
    search_fields = ['title', 'description', 'contents__content']
    resource_key = "news.moderation"
    action_key_map = {
        "list": "list",
        "retrieve": "view",
        "approve": "approve",  # maps our custom action
    }
    permission_classes = [HasDynamicPermission]

    # Optional: keep a single base queryset; access is enforced by ACL
    def get_queryset(self):
        qs = (News.objects
              .select_related('category', 'created_by')
              .prefetch_related('tags', 'contents', 'comments')
              .annotate(status_priority=News.get_status_ordering())
              .order_by('status_priority', '-modified_date'))

        # If you only moderate certain statuses, add that filter here:
        # qs = qs.filter(status__in=[News.Status.PENDING, News.Status.REVIEW])

        # Optional prefilter by a registered ScopeStrategy (if you created one for news)
        Strategy = get_strategy("news.moderation", "list")
        if self.action == "list" and Strategy:
            return Strategy().filter_queryset(qs, self.request.user)
        return qs

    # Provide object for object-level permission checks (retrieve/approve)
    def get_permission_object(self):
        if self.action in {"retrieve", "approve"} and self.kwargs.get(self.lookup_field or "pk"):
            return get_object_or_404(News, pk=self.kwargs[self.lookup_field or "pk"])
        return None

    @action(methods=['put'], detail=True, url_path='approve',
            serializer_class=NewsApprovalSerializer)
    def approve(self, request, pk=None, *args, **kwargs):
        """
        Guarded by dynamic policy:
          Resource = news.moderation
          Action   = approve
        HasDynamicPermission will object-check via get_permission_object().
        """
        instance = self.get_permission_object()  # ensures 404 and feeds object to permission
        # At this point, permission already evaluated; if denied, DRF returns 403 before here.

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data.get('status')
        instance.status = new_status
        instance.cancelled_reason = serializer.validated_data.get('cancelled_reason', None)
        instance.published_date = timezone.now()
        instance.save(update_fields=['status', 'cancelled_reason', 'published_date'])

        return Response(serializer.data)


# =================== End of testing role based access control ===================#


class NewsCommentViewSet(viewsets.GenericViewSet,
                         mixins.CreateModelMixin,
                         mixins.ListModelMixin):
    queryset = NewsComment.objects.filter(replied_to__isnull=True).order_by('created_date')
    serializer_class = NewsCommentSerializer
    search_fields = ['comment', ]
    filterset_fields = ['news', 'created_by']


class NewsLikeViewSet(viewsets.GenericViewSet,
                      mixins.CreateModelMixin,
                      mixins.ListModelMixin):
    queryset = NewsLike.objects.all()
    serializer_class = NewsLikeSerializer
    filterset_fields = ['news', 'user']


class NewsModerationHistoryViewSet(viewsets.GenericViewSet,
                                   mixins.ListModelMixin,
                                   mixins.CreateModelMixin):
    queryset = NewsModerationHistory.objects.order_by('created_date')
    serializer_class = NewsModerationHistorySerializer
    filterset_fields = ['news', ]
