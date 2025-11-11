from django.urls import include, path
import importlib
import os

app_name = 'compose'

urlpatterns = []

# Discover and load all views' urls.py automatically
views_path = os.path.join(os.path.dirname(__file__), 'views', 'v1')
for root, dirs, files in os.walk(views_path):
    for dir_name in dirs:
        try:
            module_path = f'apps.compose.views.v1.{dir_name}.urls'
            urls_module = importlib.import_module(module_path)
            urlpatterns.append(path(f'', include(urls_module)))
        except ModuleNotFoundError:
            continue
