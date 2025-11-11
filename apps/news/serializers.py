from django.db.models import F
from rest_framework import serializers

from apps.document.serializers import FileSerializer
from apps.news.models import (
    News,
    NewsCategory,
    NewsTag,
    NewsContent,
    NewsComment,
    NewsLike,
    NewsModerationHistory,
)
from config.middlewares.current_user import get_current_user_id
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField


class NewsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsCategory
        fields = ['id', 'name', 'color', 'created_date']


class NewsTagSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(queryset=NewsCategory.objects.all(), many=True)

    class Meta:
        model = NewsTag
        fields = ['id', 'name', 'categories', 'created_date']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['categories'] = NewsCategorySerializer(instance.categories, many=True).data
        return data


class NewsContentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    file = SelectItemField(model='document.File', required=False,
                           extra_field=['id', 'url', 'name', 'size', 'file_size', 'extension'])

    class Meta:
        model = NewsContent
        fields = ['id', 'content', 'file', 'type', 'created_date']


class NewsSerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model='user.User', read_only=True,
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 )
    category = SelectItemField(model='news.NewsCategory',
                               required=False,
                               extra_field=['id', 'name', 'color']
                               )
    tags = NewsTagSerializer(many=True, required=False, read_only=True)
    tags_ids = serializers.ListField(write_only=True,
                                     required=False,
                                     child=serializers.IntegerField())
    contents = NewsContentSerializer(many=True, required=False)
    image = SelectItemField(model='document.File', required=False,
                            extra_field=['id', 'url', 'name', 'size', 'file_size', 'extension'])
    galleries = FileSerializer(many=True, required=False, read_only=True)
    images_ids = serializers.ListField(write_only=True, required=False, child=serializers.IntegerField())
    is_liked = serializers.SerializerMethodField(read_only=True)
    comments_counts = serializers.SerializerMethodField(read_only=True)

    current_user = None

    @property
    def _current_user_id(self):
        if self.current_user:
            return self.current_user
        return get_current_user_id()

    class Meta:
        model = News
        fields = [
            'id',
            'title',
            'description',
            'category',
            'status',
            'tags',
            'tags_ids',
            'contents',
            'created_date',
            'modified_date',
            'published_date',
            'created_by',
            'view_counts',
            'like_counts',
            'image',
            'galleries',
            'images_ids',
            'is_liked',
            'comments_counts',
            'cancelled_reason',
        ]
        read_only_fields = [
            'is_liked',
            'like_counts',
            'tags',
            'view_counts',
            'comments_counts',
            'created_by',
            'created_date',
            'modified_date',
            'published_date',
        ]

    def get_is_liked(self, instance):
        return NewsLike.objects.filter(
            news_id=instance.id,
            user_id=self._current_user_id,
        ).exclude(emoji__isnull=True).exclude(emoji='').exists()

    def get_comments_counts(self, instance):
        return NewsComment.objects.filter(news_id=instance.id).count()

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        tags_ids = validated_data.pop('tags_ids', [])
        contents = validated_data.pop('contents', [])
        images_ids = validated_data.pop('images_ids', [])

        instance = super().create(validated_data)
        instance.tags.set(tags_ids)
        instance.galleries.set(images_ids)
        self._create_contents(instance, contents)
        return instance

    def _create_contents(self, instance, contents):
        for content in contents:
            NewsContent.objects.create(news=instance, **content)

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', [])
        tags_ids = validated_data.pop('tags_ids', [])
        contents = validated_data.pop('contents', [])
        images_ids = validated_data.pop('images_ids', [])

        instance = super().update(instance, validated_data)
        instance.tags.set(tags_ids)
        instance.galleries.set(images_ids)
        self._update_contents(instance, contents)

        return instance

    def _update_contents(self, instance, contents):
        # Map existing content by their ID (ensure IDs are strings for consistent comparison)
        existing_contents = {content.id: content for content in instance.contents.all()}

        for content in contents:
            content_id = content.get('id')  # Ensure the ID is treated as a string
            if content_id and content_id in existing_contents:
                # Update existing content
                content_item = existing_contents.pop(content_id)
                content_item.content = content.get('content', content_item.content)
                content_item.file = content.get('file', content_item.file)
                content_item.type = content.get('type', content_item.type)
                content_item.save()
            else:
                # Create new content
                NewsContent.objects.create(news=instance, **content)

        # Delete any remaining contents that were not in the updated list
        for content_item in existing_contents.values():
            content_item.delete()


class NewsApprovalSerializer(serializers.ModelSerializer):
    status = serializers.CharField(max_length=25, required=False)
    cancelled_reason = serializers.CharField(max_length=255,
                                             required=False,
                                             allow_null=True, allow_blank=True)

    class Meta:
        model = News
        fields = ['id', 'status', 'cancelled_reason']

    def validate(self, attrs):
        request = self.context.get('request')
        status = attrs.get('status')
        cancelled_reason = attrs.get('cancelled_reason')

        if status not in CONSTANTS.NEWS_STATUS.LIST:
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=status)
            raise ValidationError2(message)

        if status == CONSTANTS.NEWS_STATUS.DECLINED and not cancelled_reason:
            message = get_response_message(request, 607)
            raise ValidationError2(message)

        return attrs


class CommentReplySerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 required=False)
    replied_to = SelectItemField(model='news.NewsComment',
                                 extra_field=['id', 'created_by'],
                                 required=False)

    class Meta:
        model = NewsComment
        fields = [
            'id',
            'news',
            'comment',
            'created_by',
            'created_date',
            'replied_to',
        ]
        read_only_fields = ['created_date']


class NewsCommentSerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    replied_to = SelectItemField(model='news.NewsComment',
                                 extra_field=['id', 'created_by'],
                                 required=False)
    replies = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NewsComment
        fields = [
            'id',
            'news',
            'created_by',
            'comment',
            'created_date',
            'replied_to',
            'replies',
        ]
        read_only_fields = ['created_date']

    def get_replies(self, instance):
        if not instance.replied_to:
            return CommentReplySerializer(instance.tree.exclude(id=instance.id), many=True).data
        return []


class NewsLikeSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           read_only=True)
    emoji = serializers.CharField(max_length=25, required=False, allow_null=True)

    class Meta:
        model = NewsLike
        fields = [
            'id',
            'news',
            'emoji',
            'user',
            'created_date',
        ]
        read_only_fields = ['created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        emoji = attrs.get('emoji')

        if emoji not in CONSTANTS.NEWS_LIKE_EMOJI.LIST:
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=emoji)
            raise ValidationError2(message)

        return attrs

    def create(self, validated_data):
        user = get_current_user_id()
        news = validated_data.get('news')
        emoji = validated_data.get('emoji')
        validated_data['user_id'] = user

        # Find an existing instance, or create a new one
        instance, created = NewsLike.objects.get_or_create(news=news, user_id=user)

        if created:
            # Create a new instance, increment like count
            news.like_counts = F('like_counts') + 1
            news.save()
            news.refresh_from_db()  # Ensure `like_counts` is updated

        else:
            # Update the existing instance
            if emoji:
                # If emoji is added, increment like count
                if not instance.emoji:  # Only if emoji was not already set
                    news.like_counts = F('like_counts') + 1
                    news.save()
                    news.refresh_from_db()
            else:
                # If emoji is removed, decrement like count but not below zero
                if instance.emoji and news.like_counts > 0:
                    news.like_counts = F('like_counts') - 1
                    news.save()
                    news.refresh_from_db()  # Corrected method call

            # Update the emoji
            instance.emoji = emoji
            instance.save()

        return instance


class NewsModerationHistorySerializer(serializers.ModelSerializer):
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)

    class Meta:
        model = NewsModerationHistory
        fields = ['id', 'news', 'description', 'status', 'created_by', 'created_date']
        read_only_fields = ['created_date']

    def validate(self, attrs):
        request = self.context.get('request')
        news = attrs.get('news')
        status = attrs.get('status')

        if not news:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(object='news id')
            raise ValidationError2(message)

        if news.status == CONSTANTS.NEWS_STATUS.PUBLISHED:
            message = get_response_message(request, 646)
            raise ValidationError2(message)

        # if news.status != CONSTANTS.NEWS_STATUS.PENDING:
        #     message = get_response_message(request, 647)
        #     raise ValidationError2(message)

        if status not in [CONSTANTS.NEWS_STATUS.PUBLISHED,
                          CONSTANTS.NEWS_STATUS.DECLINED, CONSTANTS.NEWS_STATUS.PENDING]:
            message = get_response_message(request, 606)
            message['message'] = message['message'].format(object=status)
            raise ValidationError2(message)

        return attrs
