from django.db.models import Q
from rest_framework import viewsets

from apps.wcalendar.filters import CalendarModelFilter
from apps.wcalendar.models import CalendarModel
from apps.wcalendar.serializers import CalendarModelSerializer
from config.middlewares.current_user import get_current_user_id


class CalendarModelViewSet(viewsets.ModelViewSet):
    queryset = CalendarModel.objects.all()
    serializer_class = CalendarModelSerializer
    filterset_class = CalendarModelFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = get_current_user_id()
        can_see = Q(organizer_id=user_id) | Q(participants__user_id=user_id) | Q(created_by_id=user_id)
        return queryset.filter(can_see).distinct().order_by('created_date')
