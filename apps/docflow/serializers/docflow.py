from rest_framework import serializers

from apps.docflow.models import BaseDocument, DocumentFile, Reviewer
from apps.document.models import File
from apps.reference.models import ActionDescription, FieldActionMapping, StatusModel, Correspondent
from apps.reference.tasks import action_log
from apps.user.models import User
from base_model.serializers import ContentTypeMixin
from config.middlewares.current_user import get_current_user_id
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField
from utils.tools import get_or_none, get_user_ip


class DocumentFileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    file = SelectItemField(model='document.File', required=False,
                           extra_field=['id', 'name', 'url', 'size', 'file_size', 'extension'])

    class Meta:
        model = DocumentFile
        fields = [
            'file',
            'id',
        ]

    # def validate(self, attrs):
    #     file = attrs.get('file')
    #     request = self.context.get('request')
    #
    #     if not file:
    #         message = get_response_message(request, 600)
    #         message['message'] = message['message'].format(type='file')
    #         raise ValidationError2(message)
    #
    #     return attrs

    def validate_file(self, file):
        request = self.context.get('request')
        if file:
            return file.id
        get_or_none(File, request, id=file)

    def create(self, validated_data):
        file = validated_data.pop('file', None)
        instance = super().create(validated_data)
        instance.file_id = file
        instance.save()

        return instance

    def update(self, instance, validated_data):
        file = validated_data.pop('file', None)
        instance = super().update(instance, validated_data)
        instance.file_id = file
        instance.save()

        return instance


class ReviewerListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    user = SelectItemField(model='user.User', required=False,
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           )
    status = SelectItemField(model='reference.StatusModel', required=False, extra_field=['id', 'name'])
    document = serializers.PrimaryKeyRelatedField(queryset=BaseDocument.objects.all(), required=False)

    class Meta:
        model = Reviewer
        fields = [
            'comment',
            'document',
            'has_resolution',
            'id',
            'read_time',
            'status',
            'user',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        document = attrs.get('document')
        user_id = attrs.get('user')
        id = attrs.get('id', None)

        if not user_id:
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='user')
            raise ValidationError2(message)

        if not document and not request.method == 'POST':
            message = get_response_message(request, 600)
            message['message'] = message['message'].format(type='document')
            raise ValidationError2(message)

        if not id and Reviewer.objects.filter(document=document, user_id=user_id).exists():
            user = get_or_none(User, request, id=user_id)
            message = get_response_message(request, 602)
            message['message'] = message['message'].format(object=user.full_name)
            raise ValidationError2(message)

        return attrs

    def validate_user(self, user):
        """
        Validate and process the 'user' field.
        Convert provided user ID to the actual User object.
        """
        request = self.context.get('request')
        if user:
            return user.id
        get_or_none(StatusModel, request, id=user)

    def validate_status(self, status):
        """
        Validate and process the 'status' field.
        Convert provided status ID to the actual StatusModel object.
        """
        request = self.context.get('request')
        if status:
            return status.id
        get_or_none(StatusModel, request, id=status)

    def validate_document(self, document):
        """
        Validate and process the 'document' field.
        Convert provided document ID to the actual BaseDocument object.
        """

        if document:
            return document.id
        return None

    def create(self, validated_data):
        document = validated_data.pop('document')
        user = validated_data.pop('user', None)
        status = validated_data.pop('status', None)
        instance = super().create(validated_data)
        instance.user_id = user
        instance.document_id = document
        instance.status_id = StatusModel.objects.get(is_default=True).id
        instance.save()

        return instance

    def update(self, instance, validated_data):
        document = validated_data.pop('document')
        user = validated_data.pop('user', None)
        status = validated_data.pop('status', instance.status_id)
        instance = super().update(instance, validated_data)
        instance.user_id = user
        instance.document_id = document
        instance.status_id = status
        instance.save()

        return instance


class SimpleBaseDocFlowSerializer(ContentTypeMixin, serializers.ModelSerializer):
    correspondent = SelectItemField(model='reference.Correspondent', required=False,
                                    extra_field=['id', 'name', 'tin', 'type'])
    status = SelectItemField(model='reference.StatusModel', extra_field=['id', 'name'], read_only=True)
    delivery_type = SelectItemField(model='reference.DeliveryType', required=False, extra_field=['id', 'name'])
    document_type = SelectItemField(model='reference.DocumentType', required=False, extra_field=['id', 'name'])
    document_sub_type = SelectItemField(model='reference.DocumentSubType', required=False, extra_field=['id', 'name'])
    journal = SelectItemField(model='reference.Journal', required=False, extra_field=['id', 'name'])
    language = SelectItemField(model='reference.LanguageModel', required=False, extra_field=['id', 'name'])
    priority = SelectItemField(model='reference.Priority', required=False, extra_field=['id', 'name'])
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    files = DocumentFileSerializer(many=True, required=False, allow_null=True)
    compose = SelectItemField(model='compose.Compose', required=False,
                              extra_field=['id', 'register_number', 'document_type', 'document_sub_type'])

    class Meta:
        model = BaseDocument
        fields = [
            'code',
            'compose',
            'content_type',
            'correspondent',
            'created_by',
            'created_date',
            'delivery_type',
            'description',
            'document_type',
            'document_sub_type',
            'files',
            'grif',
            'id',
            'journal',
            'language',
            'modified_date',
            'number_of_papers',
            'outgoing_date',
            'outgoing_number',
            'priority',
            'register_date',
            'register_number',
            'status',
            'title',
        ]


class BaseDocFlowSerializer(ContentTypeMixin, serializers.ModelSerializer):
    correspondent = SelectItemField(model='reference.Correspondent', required=False,
                                    extra_field=['id', 'name', 'tin', 'type'])
    status = SelectItemField(model='reference.StatusModel', extra_field=['id', 'name'], read_only=True)
    delivery_type = SelectItemField(model='reference.DeliveryType', required=False, extra_field=['id', 'name'])
    document_type = SelectItemField(model='reference.DocumentType', required=False, extra_field=['id', 'name'])
    journal = SelectItemField(model='reference.Journal', required=False, extra_field=['id', 'name'])
    language = SelectItemField(model='reference.LanguageModel', required=False, extra_field=['id', 'name'])
    priority = SelectItemField(model='reference.Priority', required=False, extra_field=['id', 'name'])
    created_by = SelectItemField(model='user.User',
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    files = DocumentFileSerializer(many=True, required=False, allow_null=True)
    reviewers = ReviewerListSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = BaseDocument
        fields = [
            'code',
            'content_type',
            'company',
            'correspondent',
            'created_by',
            'created_date',
            'delivery_type',
            'short_description',
            'description',
            'document_type',
            'files',
            'grif',
            'id',
            'journal',
            'language',
            'modified_date',
            'number_of_papers',
            'outgoing_date',
            'outgoing_number',
            'priority',
            'register_date',
            'register_number',
            'reviewers',
            'title',
            'status',
        ]

    def validate(self, attrs):
        journal = attrs.get('journal')
        document_type = attrs.get('document_type')
        request = self.context.get('request')
        message = get_response_message(request, 600)

        if not journal:
            message['message'] = message['message'].format(type='journal')
            raise ValidationError2(message)

        if not document_type:
            message['message'] = message['message'].format(type='document_type')
            raise ValidationError2(message)

        return attrs

    def validate_files(self, files):
        if files:
            return files
        return []

    def validate_reviewers(self, reviewers):
        if reviewers:
            return reviewers
        return []

    def create(self, validated_data):
        request = self.context.get('request')
        files = validated_data.pop('files', [])
        reviewers = validated_data.pop('reviewers', [])
        instance = super().create(validated_data)
        status = get_or_none(StatusModel, request, is_default=True)
        instance.status_id = status.id
        instance.save()

        if files:
            for file in files:
                DocumentFile.objects.create(document=instance, file_id=file.get('file'))

        if reviewers:
            for reviewer in reviewers:
                Reviewer.objects.create(document=instance, status_id=status.id, user_id=reviewer.get('user'))

        # write activity log for created base document
        user_id = get_current_user_id()
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(instance)
        action_log.apply_async(
            (user_id, 'created', '100', ct_id,
             instance.id, user_ip, instance.register_number), countdown=3)
        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        files = validated_data.pop('files', [])
        reviewers = validated_data.pop('reviewers', [])
        original_instance = self.Meta.model.objects.get(pk=instance.pk)
        user_ip = get_user_ip(request)
        ct_id = self.get_content_type(instance)
        user_id = get_current_user_id()

        for field_name in validated_data:
            old_value = getattr(original_instance, field_name)
            instance = super().update(instance, validated_data)
            new_value = getattr(instance, field_name)

            action_mapping = FieldActionMapping.objects.filter(field_name=field_name).first()
            if action_mapping and old_value != new_value:
                action_log.apply_async(
                    (user_id, 'updated', action_mapping.action_code,
                     ct_id, instance.pk, user_ip, old_value, new_value), countdown=3)

        self.update_nested_serializers(instance, DocumentFileSerializer, files, 'files')
        self.update_nested_serializers(instance, ReviewerListSerializer, reviewers, 'reviewers')

        return instance

    def update_nested_serializers(self, instance, nested_serializer_class, nested_data, related_name):
        """
        Update nested serializers for the given instance.

        Parameters:
            instance: The instance for which nested serializers need to be updated.
            nested_serializer_class: The class of the nested serializer to use.
            nested_data: The data containing the nested serializer information.
            related_name: The related_name of the reverse relation in the instance.

        Example usage:
            update_nested_serializers(project_instance, DocumentFileSerializer, files, 'files')
        """
        nested_items = dict((i.id, i) for i in getattr(instance, related_name).all())
        nested_serializer_model = nested_serializer_class.Meta.model
        request = self.context.get('request')
        user_ip = get_user_ip(request)
        user_id = get_current_user_id()
        ct_id = self.get_content_type(instance)

        for item in nested_data:
            if 'id' in item:
                instance_id = item.get('id')
                get_or_none(nested_serializer_model, request, id=instance_id)
                nested_instance = nested_items.pop(item['id'])
                nested_serializer = nested_serializer_class(nested_instance, data=item, context={'request': request})

                if nested_serializer.is_valid():
                    nested_serializer.save()
            else:
                nested_serializer = nested_serializer_class(data=item, context={'request': request})
                nested_serializer.is_valid(raise_exception=True)
                nested_serializer.save(document=instance)

                if related_name == 'reviewers':
                    user_id = nested_serializer.validated_data.get('user')
                    user = get_or_none(User, request, id=user_id)
                    action_log.apply_async(
                        (user_id, 'created', '115', ct_id,
                         instance.id, user_ip, user.full_name), countdown=3)

                if related_name == 'files':
                    file_id = nested_serializer.validated_data.get('file')
                    file = get_or_none(File, request, id=file_id)
                    action_log.apply_async(
                        (user_id, 'created', '116', ct_id,
                         instance.id, user_ip, file.name), countdown=3)

        # print(nested_items)
        if len(nested_items) > 0:
            for item in nested_items.values():
                if related_name == 'reviewers':
                    user = item.user
                    action_log.apply_async(
                        (user_id, 'updated', '117', ct_id,
                         instance.id, user_ip, user.full_name, None), countdown=3)

                if related_name == 'files':
                    file = item.file
                    action_log.apply_async(
                        (user_id, 'updated', '118', ct_id,
                         instance.id, user_ip, file.name, None), countdown=3)

                item.delete()


class SimpleResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    value = serializers.CharField()
