from django.apps import AppConfig


class ComposeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compose'
    verbose_name = 'Compose (Sending Documents)'
