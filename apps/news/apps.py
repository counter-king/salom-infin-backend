from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.news'

    def ready(self):
        from apps.news.signals import save_top_level_comment_id
