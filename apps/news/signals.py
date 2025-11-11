from django.db.models.signals import post_save

from apps.news.models import NewsComment


def save_top_level_comment_id(sender, instance, created, **kwargs):
    if created:
        if instance.replied_to:
            instance.top_level_comment_id = instance.replied_to.top_level_comment_id
        else:
            instance.top_level_comment_id = instance.id
        instance.save()


post_save.connect(save_top_level_comment_id, sender=NewsComment)
