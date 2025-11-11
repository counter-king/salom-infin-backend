from django.db import models
from django.db.models import Case, When, Value, IntegerField

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class NewsCategory(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=25, null=True, blank=True)

    def __str__(self):
        return f'{self.id} - {self.name}'

    class Meta:
        verbose_name = 'News Category'
        verbose_name_plural = 'News Categories'


class NewsTag(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    categories = models.ManyToManyField(NewsCategory, blank=True, related_name='tags')

    def __str__(self):
        return f'{self.id}'

    class Meta:
        verbose_name = 'News Tag'
        verbose_name_plural = 'News Tags'


class News(BaseModel):
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(NewsCategory,
                                 on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='news')
    tags = models.ManyToManyField(NewsTag, related_name='news')
    image = models.ForeignKey('document.File',
                              on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='+')
    view_counts = models.IntegerField(default=0)
    like_counts = models.IntegerField(default=0)
    galleries = models.ManyToManyField('document.File', blank=True, related_name='+')
    published_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50,
                              choices=CONSTANTS.NEWS_STATUS.CHOICES,
                              default=CONSTANTS.NEWS_STATUS.DEFAULT,
                              null=True, blank=True)
    cancelled_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'News'
        verbose_name_plural = 'News'

    @staticmethod
    def get_status_ordering():
        return Case(
            When(status=CONSTANTS.NEWS_STATUS.PENDING, then=Value(0)),
            When(status=CONSTANTS.NEWS_STATUS.DECLINED, then=Value(1)),
            When(status=CONSTANTS.NEWS_STATUS.PUBLISHED, then=Value(2)),
            When(status=CONSTANTS.NEWS_STATUS.DRAFT, then=Value(3)),
            When(status=CONSTANTS.NEWS_STATUS.ARCHIVED, then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        )


class NewsContent(BaseModel):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='contents')
    content = models.TextField(null=True, blank=True)
    file = models.ForeignKey('document.File',
                             on_delete=models.SET_NULL,
                             null=True, blank=True)
    type = models.CharField(max_length=25,
                            null=True, blank=True,
                            choices=CONSTANTS.NEWS_CONTENT_TYPE.CHOICES)

    def __str__(self):
        return self.news.title

    class Meta:
        verbose_name = 'News Content'
        verbose_name_plural = 'News Contents'
        ordering = ['created_date']


class NewsViewer(BaseModel):
    news = models.ForeignKey(News,
                             on_delete=models.CASCADE,
                             related_name='viewers')
    viewer = models.ForeignKey('user.User',
                               on_delete=models.SET_NULL,
                               null=True,
                               related_name='viewed_news')

    def __str__(self):
        return self.viewer.full_name

    class Meta:
        verbose_name = 'News Viewer'
        verbose_name_plural = 'News Viewers'


class NewsComment(BaseModel):
    news = models.ForeignKey(News,
                             on_delete=models.CASCADE,
                             related_name='comments')
    comment = models.TextField(null=True, blank=True)
    user = models.ForeignKey('user.User',
                             on_delete=models.SET_NULL,
                             null=True,
                             related_name='comments')
    replied_to = models.ForeignKey('self',
                                   on_delete=models.CASCADE,
                                   blank=True, null=True,
                                   related_name='replies')
    top_level_comment_id = models.PositiveBigIntegerField(null=True, blank=True)

    def __str__(self):
        return self.news.title

    @property
    def tree(self):
        return NewsComment.objects.filter(top_level_comment_id=self.id)

    class Meta:
        verbose_name = 'News Comment'
        verbose_name_plural = 'News Comments'

    def as_select_item(self):
        return {
            'comment_id': self.id,
            'created_by': self.created_by.as_select_item(),
            'created_date': self.created_date,
        }


class NewsLike(BaseModel):
    news = models.ForeignKey(News,
                             on_delete=models.CASCADE,
                             related_name='likes')
    user = models.ForeignKey('user.User',
                             on_delete=models.SET_NULL,
                             null=True,
                             related_name='liked_news')
    emoji = models.CharField(max_length=25,
                             choices=CONSTANTS.NEWS_LIKE_EMOJI.CHOICES,
                             null=True, blank=True)

    def __str__(self):
        return self.news.title

    class Meta:
        verbose_name = 'News Like'
        verbose_name_plural = 'News Likes'


class NewsModerationHistory(BaseModel):
    description = models.TextField(null=True)
    status = models.CharField(max_length=50,
                              choices=CONSTANTS.NEWS_STATUS.CHOICES,
                              default=CONSTANTS.NEWS_STATUS.DEFAULT,
                              null=True, blank=True)
    news = models.ForeignKey(News, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f'{self.news}'

    class Meta:
        verbose_name_plural = 'News Moderation Histories'
