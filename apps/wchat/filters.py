import django_filters

from apps.wchat.models import ChatMessage


class MessageLinkFilter(django_filters.FilterSet):
    chat = django_filters.NumberFilter(field_name="chat", required=True)
    type = django_filters.CharFilter(field_name="type")

    class Meta:
        model = ChatMessage
        fields = ['chat', 'type']
