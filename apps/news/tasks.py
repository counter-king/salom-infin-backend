from celery import shared_task

from config.celery import app
from apps.news.models import News, NewsViewer


@app.task(max_retries=1)
def update_news_view_count(news_id, user_id):
    news_viewer = NewsViewer.objects.filter(news_id=news_id, viewer_id=user_id).first()

    if not news_viewer:
        NewsViewer.objects.create(news_id=news_id, viewer_id=user_id)
        news = News.objects.get(id=news_id)
        news.view_counts += 1
        news.save()
    return 'ok'
