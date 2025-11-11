from rest_framework import serializers

from apps.document.models import File
from apps.document.serializers import FileSerializer
from apps.wcalendar.models import CalendarModel, CalendarParticipant
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField, serialize_m2m
from utils.tools import send_sms_to_phone


class CalendarParticipantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           )

    class Meta:
        model = CalendarParticipant
        fields = ['id', 'user', 'is_informed', 'is_accepted']


class CalendarModelSerializer(serializers.ModelSerializer):
    participants = CalendarParticipantSerializer(many=True, required=False)
    organizer = SelectItemField(model='user.User',
                                extra_field=['id', 'full_name', 'position', 'department'],
                                required=False)
    attachments = FileSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = CalendarModel
        fields = [
            'id',
            'title',
            'start_date',
            'end_date',
            'description',
            'organizer',
            'attachments',
            'priority',
            'type',
            'participants',
            'source',
            'link',
            'notify_by',
            'status',
        ]
        read_only_fields = ['status']

    def validate(self, attrs):
        request = self.context.get('request')
        type = attrs.get('type')
        participants = attrs.get('participants', [])
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        notify_by = attrs.get('notify_by')
        source = attrs.get('source')

        if type == 'event':
            if not participants:
                message = get_response_message(request, 600)
                message['message'] = message['message'].format(type='participants')
                raise ValidationError2(message)

            if not notify_by:
                message = get_response_message(request, 600)
                message['message'] = message['message'].format(type='notify_by')
                raise ValidationError2(message)

        if not start_date:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='start_date')
            raise ValidationError2(message)

        return attrs

    def notify_participants_by_sms(self, phones: list, text: str):
        """
        Notify participants by sms about the event
        """
        for phone in phones:
            # send sms
            send_sms_to_phone(phone, text)

    def create(self, validated_data):
        participants = validated_data.pop('participants', [])
        attachments = validated_data.pop('attachments', [])
        notify_by = validated_data.get('notify_by', None)
        calendar = CalendarModel.objects.create(**validated_data)

        serialize_m2m('create', File, 'attachments', attachments, calendar)
        user_phones = []

        for participant in participants:
            CalendarParticipant.objects.create(calendar=calendar, **participant)
            user_phones.append(participant['user'].phone)

        start_date = calendar.start_date.strftime('%d-%m-%Y %H:%M')
        end_date = calendar.end_date.strftime('%d-%m-%Y %H:%M') if calendar.end_date else "Noma'lum"

        if notify_by == 'sms':
            text = f"Salom! Sizda {start_date} sanasida {calendar.source} orqali tadbiringiz bor. Tugash vaqti: {end_date}"
            self.notify_participants_by_sms(user_phones, text)

        return calendar

    def update(self, instance, validated_data):
        participants = validated_data.pop('participants', [])
        attachments = validated_data.pop('attachments', [])
        calendar = super().update(instance, validated_data)

        serialize_m2m('update', File, 'attachments', attachments, calendar)

        if participants:
            self.update_participants(participants)

        return calendar

    def update_participants(self, participants: list):
        participant_items = dict((i.id, i) for i in self.instance.participants.all())

        for item in participants:
            if 'id' in item:
                # if exists id pop from the dict and update
                participant_by_item = participant_items.pop(item['id'])
                participant_by_item.is_informed = item.get('is_informed', False)
                participant_by_item.is_accepted = item.get('is_accepted', None)
                participant_by_item.save()
            else:
                CalendarParticipant.objects.create(calendar=self.instance, **item)

        if len(participant_items) > 0:
            for item in participant_items.values():
                item.delete()
