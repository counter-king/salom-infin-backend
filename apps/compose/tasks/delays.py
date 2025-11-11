"""
Here we define the tasks that are used to delay some tasks in the compose app.
To optimize the performance of the application.

Because some tasks do not need to be executed immediately.
So, the server may breath for some time )
"""

import logging
import requests
from collections import OrderedDict, defaultdict

from celery import shared_task

from apps.compose.models import Compose, ComposeVersionModel
from config.celery import app


@app.task(max_retries=1)
def create_compose_version(compose_id: int, old_text: str, new_text: str, user_id: int):
    """
    Compose a version creation task, it is used to show the difference
    between the old version and the new version
    """
    compose = Compose.objects.get(pk=compose_id)
    ComposeVersionModel.create_history(
        old_text=old_text,
        new_text=new_text,
        history_for=compose,
        user_id=user_id,

    )
