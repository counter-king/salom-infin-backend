from django.apps import AppConfig


class DocflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.docflow'
    verbose_name = 'Document Flow'

    def ready(self):
        import apps.docflow.signals
