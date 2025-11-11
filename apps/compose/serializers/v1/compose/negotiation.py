from rest_framework import serializers

from apps.compose.models import (
    Negotiation,
    NegotiationType,
    NegotiationInstance,
    Negotiator,
    NegotiationSubType,
)
from apps.user.models import User
from apps.user.serializers import UserSerializer
from config.middlewares.current_user import get_current_user_id
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField
from utils.tools import get_or_none


class NegotiationTypeSerializer(serializers.ModelSerializer):
    docs_count_to_sign = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NegotiationType
        fields = ['id', 'name', 'description', 'docs_count_to_sign', 'created_date']

    def get_docs_count_to_sign(self, obj):
        user_id = get_current_user_id()
        return Negotiator.objects.filter(negotiation__doc_type_id=obj.id, user_id=user_id, is_signed=None).count()


class NegotiationSubTypeSerializer(serializers.ModelSerializer):
    doc_type = SelectItemField(model='compose.NegotiationType', extra_field=['id', 'name'], required=False)

    class Meta:
        model = NegotiationSubType
        fields = ['id', 'name', 'description', 'doc_type', 'created_date']


class NegotiationSerializer(serializers.ModelSerializer):
    doc_type = SelectItemField(model='compose.NegotiationType', extra_field=['id', 'name'], required=False)
    doc_sub_type = SelectItemField(model='compose.NegotiationSubType', extra_field=['id', 'name'], required=False)
    users = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, required=False)

    class Meta:
        model = Negotiation
        fields = [
            'content',
            'created_date',
            'doc_sub_type',
            'doc_type',
            'for_new_users',
            'id',
            'title',
            'users',
        ]

    def to_representation(self, instance):
        data = super(NegotiationSerializer, self).to_representation(instance)
        users = instance.users.all()
        users = UserSerializer(users, many=True).data
        data['users'] = users
        return data

    def validate(self, attrs):
        request = self.context.get('request')
        users = attrs.get('users')
        doc_type = attrs.get('doc_type')
        doc_sub_type = attrs.get('doc_sub_type')

        if not users:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='users')
            raise ValidationError2(message)
        else:
            for user in users:
                get_or_none(User, request, id=user.id)

        if not doc_type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='doc_type')
            raise ValidationError2(message)
        else:
            get_or_none(NegotiationType, request, id=doc_type.id)

        if not doc_sub_type:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='doc_sub_type')
            raise ValidationError2(message)
        else:
            get_or_none(NegotiationSubType, request, id=doc_sub_type.id)

        return attrs

    def replace_user_variables(self, content, user_data):
        # Iterate through each key-value pair in the user_data dictionary
        for key, value in user_data.items():
            # Create the placeholder in the format {key}, e.g., {last_name}
            placeholder = f'{{{key}}}'
            # Replace the placeholder in the content with the actual value from user_data
            content = content.replace(placeholder, value if value else '')
        return content

    def create(self, validated_data):
        request = self.context.get('request')
        users = validated_data.pop('users', [])
        instance = Negotiation.objects.create(**validated_data)

        instance.users.set(users)

        # create negotiation instance for each user
        # in order to keep track of each user's negotiation
        for user in users:
            # user = User.objects.get(id=user_id)
            user_data = {
                "last_name": user.last_name,
                "first_name": user.first_name,
                "father_name": user.father_name if user.father_name else '',
                "department": user.top_level_department.name if user.top_level_department else '',
                "division": user.department.name if user.department else '',
                "position": user.position.name if user.position else '',
            }
            normalized_content = self.replace_user_variables(instance.content, user_data)
            negotiation_instance = NegotiationInstance.objects.create(
                negotiation=instance,
                doc_type_id=instance.doc_type_id,
                doc_sub_type_id=instance.doc_sub_type_id,
                content=normalized_content)
            Negotiator.objects.create(negotiation=negotiation_instance, user_id=user.id)

        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        users = validated_data.pop('users', [])

        # Update the main instance with the provided validated data
        instance = super(NegotiationSerializer, self).update(instance, validated_data)

        # Update the users associated with the negotiation instance
        instance.users.set(users)

        negotiation_instances = NegotiationInstance.objects.filter(negotiation=instance)
        existing_user_ids = set(negotiation_instances.values_list('negotiator__user_id', flat=True))
        new_user_ids = set(user.id for user in users)

        # Process users: Add or update negotiation instances
        for user in users:
            user_data = {
                "last_name": user.last_name,
                "first_name": user.first_name,
                "father_name": user.father_name if user.father_name else '',
                "department": user.top_level_department.name if user.top_level_department else '',
                "division": user.department.name if user.department else '',
                "position": user.position.name if user.position else '',
            }
            normalized_content = self.replace_user_variables(instance.content, user_data)

            if user.id not in existing_user_ids:
                # Create a new negotiation instance if it does not exist
                negotiation_instance = NegotiationInstance.objects.create(
                    negotiation=instance,
                    doc_type_id=instance.doc_type_id,
                    doc_sub_type_id=instance.doc_sub_type_id,
                    content=normalized_content
                )
                Negotiator.objects.create(negotiation=negotiation_instance, user=user)
            else:
                # Update content if the negotiation instance already exists
                negotiation_instance = negotiation_instances.filter(negotiator__user_id=user.id).first()
                negotiation_instance.content = normalized_content
                negotiation_instance.doc_type_id = instance.doc_type_id
                negotiation_instance.doc_sub_type_id = instance.doc_sub_type_id
                negotiation_instance.save()

        # Remove negotiation instances for users that are no longer associated
        outdated_instances = negotiation_instances.filter(negotiator__user_id__in=(existing_user_ids - new_user_ids))
        outdated_instances.delete()

        return instance


class NegotiatorSerializer(serializers.ModelSerializer):
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    negotiation = SelectItemField(model='compose.NegotiationInstance',
                                  extra_field=['id', 'content', 'doc_type', 'doc_sub_type'], required=False)

    class Meta:
        model = Negotiator
        fields = [
            'action_date',
            'comment',
            'created_date',
            'id',
            'is_signed',
            'negotiation',
            'user',
        ]


class NegotiateSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=True)
    pkcs7 = serializers.CharField(max_length=100000000000, required=True)


class NegotiationInstanceSerializer(serializers.ModelSerializer):
    doc_type = SelectItemField(model='compose.NegotiationType', extra_field=['id', 'name'], required=False)
    doc_sub_type = SelectItemField(model='compose.NegotiationSubType', extra_field=['id', 'name'], required=False)
    negotiators = NegotiatorSerializer(many=True, required=False)

    class Meta:
        model = NegotiationInstance
        fields = ['id', 'negotiation', 'doc_type', 'doc_sub_type', 'negotiators']
