from django.utils import timezone
from rest_framework import serializers

from apps.docflow.models import Reviewer, Assignment, Assignee
from apps.docflow.serializers import SimpleBaseDocFlowSerializer
from apps.document.models import File
from apps.document.serializers import FileSerializer
from apps.reference.models import StatusModel
from apps.reference.tasks import action_log
from config.middlewares.current_user import get_current_user_id
from utils.exception import get_response_message, ValidationError2
from utils.serializer import SelectItemField, serialize_m2m
from utils.tools import get_parents, get_user_ip, get_content_type_id


class RecursiveSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class ReviewerSerializer(serializers.ModelSerializer):
    document = SimpleBaseDocFlowSerializer(read_only=True)
    status = SelectItemField(model='reference.StatusModel', extra_field=['id', 'name'], read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    for_reviewers = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Reviewer
        fields = [
            'created_date',
            'comment',
            'document',
            'has_resolution',
            'id',
            'is_read',
            'read_time',
            'status',
            'user',
            'for_reviewers',

        ]

    def serialize_user_light(self, user):
        return {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'father_name': user.father_name,
            'full_name': user.full_name,  # if expensive, you can replace with custom annotation
            'color': user.color,
            'avatar': user.avatar.dict() if user.avatar else None,
            'status': user.status.dict() if user.status else None,
            'position': user.position.dict() if user.position else None,
            'top_level_department': user.top_level_department.dict() if user.top_level_department else None,
            'cisco': user.cisco,
            'email': user.email,
            'company': user.company.dict() if user.company else None,
            'department': user.department.dict() if user.department else None,
        }

    def get_for_reviewers(self, obj):
        reviewers = (
            Reviewer.objects
            .select_related(
                'user',
                'user__status', 'user__company',
                'user__position', 'user__department',
                'user__top_level_department'
            )
            .only(
                'user__id', 'user__first_name', 'user__last_name', 'user__father_name',
                'user__color', 'user__avatar',
                'user__status', 'user__position', 'user__top_level_department',
                'user__cisco', 'user__email', 'user__company', 'user__department'
            )
            .filter(document_id=obj.document_id)
        )

        return [self.serialize_user_light(reviewer.user) for reviewer in reviewers if reviewer.user]


class ChangeReviewerSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=500, write_only=True)
    document = serializers.IntegerField(required=False, write_only=True)
    user = serializers.IntegerField(required=False, write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        comment = attrs.get('comment', None)
        document = attrs.get('document', None)
        user = attrs.get('user', None)

        if not document:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='document')
            raise ValidationError2(msg)

        if not user:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='user')
            raise ValidationError2(msg)

        if not comment:
            msg = get_response_message(request, 607)
            raise ValidationError2(msg)

        return attrs


class VerifyOrRejectResolutionSerializer(serializers.Serializer):
    assignment_ids = serializers.ListField(required=False, child=serializers.IntegerField())
    is_verified = serializers.BooleanField(required=True)
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=500)
    pkcs7 = serializers.CharField(required=False, max_length=1000000000000000, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get('request')
        is_verified = attrs.get('is_verified', False)
        comment = attrs.get('comment', None)
        pkcs7 = attrs.get('pkcs7', None)
        assignment_ids = attrs.get('assignment_ids', None)

        # if is_verified and not pkcs7:
        #     msg = get_response_message(request, 204)  # 'pkcs7 not generated'
        #     raise ValidationError2(msg)

        if not assignment_ids:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='assignment_ids')
            raise ValidationError2(msg)

        if not isinstance(assignment_ids, list):
            msg = get_response_message(request, 606)
            msg['message'] = msg['message'].format(object='assignment_ids')
            raise ValidationError2(msg)

        if not is_verified and not comment:
            msg = get_response_message(request, 617)  # 'Iltimos izoh qoldiring'
            raise ValidationError2(msg)
        return attrs


class AssigneesSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    created_by = SelectItemField(model="user.User",
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True)
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name', 'is_default'], required=False)

    class Meta:
        model = Assignee
        fields = [
            'assignment',
            'content',
            'created_by',
            'id',
            'is_controller',
            'is_performed',
            'is_read',
            'is_responsible',
            'parent',
            'performed_date',
            'read_time',
            'status',
            'user',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        user_id = attrs.get('user')
        if user_id:
            qs = Assignee.objects.filter(user_id=user_id, assignment_id=attrs.get('assignment'))
            if qs.exists():
                msg = get_response_message(request, 602)
                msg['message'] = msg['message'].format(object=qs.first().user.full_name)
                raise ValidationError2(msg)
        return attrs


class AssignmentSerializer(serializers.ModelSerializer):
    _current_user_id = None

    @property
    def current_user_id(self):
        if not self._current_user_id:
            self._current_user_id = get_current_user_id()
        return self._current_user_id

    assignees = AssigneesSerializer(many=True, required=False)
    content = serializers.CharField(required=False, max_length=500)
    created_by = SelectItemField(model="user.User",
                                 extra_field=['full_name', 'first_name', 'last_name',
                                              'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                              'top_level_department', 'department', 'company', 'email'],
                                 read_only=True
                                 )
    reviewer = SelectItemField(model="docflow.Reviewer", extra_field=['id', 'user', 'document'], required=False)

    class Meta:
        model = Assignment
        fields = [
            'assignees',
            'content',
            'created_by',
            'created_date',
            'deadline',
            'id',
            'is_project_resolution',
            'is_verified',
            'receipt_date',
            'reviewer',
            'type',
            'parent',
        ]
        read_only_fields = ['is_verified', 'receipt_date']

    def validate(self, attrs):
        request = self.context.get('request')
        review = attrs.get('reviewer')
        content = attrs.get('content')
        type = attrs.get('type')
        deadline = attrs.get('deadline')
        assignees = attrs.get('assignees')

        if not assignees:
            msg = get_response_message(request, 615)
            raise ValidationError2(msg)

        if not review:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='reviewer')
            raise ValidationError2(msg)

        if not content:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='content')
            raise ValidationError2(msg)

        if not type:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='type')
            raise ValidationError2(msg)

        if type == 'control_point' and not deadline:
            msg = get_response_message(request, 614)
            raise ValidationError2(msg)

        return attrs

    def record_activity(self, instance, user, action=None, is_controller=False):
        request = self.context.get('request')
        user_ip = get_user_ip(request)
        user_id = get_current_user_id()
        ct_id = get_content_type_id(instance.reviewer.document)
        document_id = instance.reviewer.document_id

        if action == 'deleted':
            if is_controller is True:
                description_code = "131"
            else:
                description_code = "132"

            action_log.apply_async(
                (user_id, 'deleted', description_code,
                 ct_id, document_id, user_ip, user.full_name), countdown=2)
        else:
            if is_controller is True:
                description_code = "130"
            else:
                description_code = "129"

            action_log.apply_async(
                (user_id, 'created', description_code,
                 ct_id, document_id, user_ip, user.full_name), countdown=2)

    def check_duplicates(self, instance, assignees, **kwargs):
        """
        Check for duplicate assignees.

        This method checks the provided 'assignments' data for duplicate assignees.
        If a duplicate assignee is found, the method raises a ValidationError.

        Parameters:
        - assignments (list): A list of dictionaries representing the updated assignees data.
          Each dictionary contains information about an assignee, including the assignee's ID (if it exists) and other data.
          If the assignee's ID exists in the dictionary, the method will update the existing assignee.
          If the assignee's ID is not present, the method will create a new assignee with the provided data.

        """
        request = self.context.get('request')
        parent = kwargs.get('parent', None)
        if parent:
            assignment_ids = get_parents(Assignment, parent.id)
        else:
            assignment_ids = get_parents(Assignment, instance.id)

        for index, assignee in enumerate(assignees):
            user = assignee.get('user')
            assignee_check = Assignee.objects.filter(user_id=user, assignment_id__in=assignment_ids)
            if assignee_check.exists():
                msg = get_response_message(request, 602)
                msg['message'] = msg['message'].format(object=user.full_name)
                raise ValidationError2(msg)

    def create(self, validated_data):
        assignees = validated_data.pop('assignees')
        parent = validated_data.pop('parent', None)
        instance = Assignment.objects.create(**validated_data)
        status_id = StatusModel.objects.get(is_default=True).id

        if instance.is_project_resolution is True:
            instance.reviewer.has_resolution = True
            instance.reviewer.save()
        else:
            instance.receipt_date = timezone.now()
            instance.is_verified = True
            instance.has_child_resolution = True

        if parent:
            self.check_duplicates(instance, assignees, parent=parent)
        else:
            self.check_duplicates(instance, assignees)
        instance.parent = parent
        instance.save()

        for index, assignee in enumerate(assignees):
            user = assignee.get('user')
            is_controller = assignee.get('is_controller', False)
            is_responsible = assignee.get('is_responsible', False)
            assignee_type = Assignee.objects.create(assignment=instance, status_id=status_id, user=user,
                                                    is_controller=is_controller, is_responsible=is_responsible)

            # notify users about this action if not project resolution
            self.record_activity(instance, user, assignee_type.is_controller)

        return instance

    def update(self, instance, validated_data):
        assignees = validated_data.pop('assignees')
        status_id = StatusModel.objects.get(is_default=True).id
        instance = super().update(instance, validated_data)
        self.update_assignees(assignees, status_id)

        return instance

    def update_assignees(self, assignees, status_id):
        """
        Update assignees for the current instance.

        This method updates the assignees associated with the current instance based on the provided 'assignments' data.

        Parameters:
        - assignments (list): A list of dictionaries representing the updated assignees data.
          Each dictionary contains information about an assignee, including the assignee's ID (if it exists) and other data.
          If the assignee's ID exists in the dictionary, the method will update the existing assignee.
          If the assignee's ID is not present, the method will create a new assignee with the provided data.

        - status_id (int): The status ID to set for new assignees.

        """
        # Create a dictionary of assignment IDs and their corresponding AssignmentUser objects for easy lookup.
        assignment_items = dict((i.id, i) for i in self.instance.assignees.all())

        for item in assignees:
            if 'id' in item:
                # If the 'id' exists in the dictionary, remove it and update the existing assignee.
                assignment = assignment_items.pop(item['id'])
                assignment.is_responsible = item.get('is_responsible', False)
                assignment.save()
            else:
                # If the 'id' does not exist, create a new AssignmentUser with the provided data.
                user = item.get('user')
                assignee_type = Assignee.objects.create(assignment=self.instance, status_id=status_id, user=user)

                # notify users about this action if not project resolution
                self.record_activity(self.instance, user, assignee_type.is_controller)

        # Any remaining assignment_items in the dictionary represent assignees that were not included in the update,
        # so they should be deleted from the database.
        if len(assignment_items) > 0:
            for item in assignment_items.values():
                user = item.user
                item.delete()
                self.record_activity(self.instance, user, action='deleted', is_controller=item.is_controller)


class MyResolutionSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'document', 'type', 'receipt_date', 'deadline', 'is_verified', 'is_project_resolution']

    def get_document(self, obj):
        document = obj.reviewer.document
        return SimpleBaseDocFlowSerializer(document).data


class MyResolutionDetailSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField(read_only=True)
    assignees = AssigneesSerializer(many=True, required=False)

    class Meta:
        model = Assignment
        fields = [
            'id',
            'assignees',
            'document',
            'type',
            'receipt_date',
            'deadline',
            'is_verified',
            'is_project_resolution',
        ]

    def get_document(self, obj):
        document = obj.reviewer.document
        return SimpleBaseDocFlowSerializer(document).data


class MyAssignmentSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField(read_only=True)
    assignment = SelectItemField(model="docflow.Assignment",
                                 extra_field=['id', 'type', 'created_date', 'reviewer', 'is_verified', 'receipt_date',
                                              'deadline', 'content'],
                                 read_only=True)
    user = SelectItemField(model="user.User",
                           extra_field=['id', 'first_name', 'last_name', 'color'],
                           read_only=True
                           )
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name', 'is_default'], read_only=True)
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Assignee
        fields = [
            'assignment',
            'content',
            'created_date',
            'document',
            'files',
            'id',
            'is_controller',
            'is_performed',
            'is_read',
            'is_responsible',
            'performed_date',
            'read_time',
            'status',
            'user',
        ]

    def get_document(self, obj):
        document = obj.assignment.reviewer.document
        return SimpleBaseDocFlowSerializer(document).data


class PerformerSerializer(serializers.ModelSerializer):
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           read_only=True)
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name'], read_only=False)

    class Meta:
        model = Assignee
        fields = [
            'content',
            'created_date',
            'id',
            'is_controller',
            'is_performed',
            'is_read',
            'is_responsible',
            'modified_date',
            'performed_date',
            'status',
            'user',
        ]


class PerformSerializer(serializers.ModelSerializer):
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name'], read_only=True)
    content = serializers.CharField(max_length=2000, required=False, allow_null=True, allow_blank=True)
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Assignee
        fields = [
            'content',
            'files',
            'is_performed',
            'modified_date',
            'performed_date',
            'status',
        ]
        read_only_fields = ['is_performed', 'performed_date', 'modified_date']

    def validate(self, attrs):
        request = self.context.get('request')
        content = attrs.get('content', None)

        if not content:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='content')
            raise ValidationError2(msg)

        return attrs

    def update(self, instance, validated_data):
        files = validated_data.pop('files', [])
        instance = super().update(instance, validated_data)
        serialize_m2m('update', File, 'files', files, instance)

        return instance


class ReviewerDetailSerializer(serializers.ModelSerializer):
    document = SimpleBaseDocFlowSerializer(read_only=True)
    status = SelectItemField(model='reference.StatusModel', extra_field=['id', 'name'], read_only=True)
    user = SelectItemField(model='user.User',
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           required=False)
    assignments = serializers.SerializerMethodField(read_only=True)
    reviewers = serializers.SerializerMethodField(read_only=True)
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Reviewer
        fields = [
            'assignments',
            'created_date',
            'modified_date',
            'comment',
            'document',
            'has_resolution',
            'files',
            'id',
            'is_read',
            'read_time',
            'reviewers',
            'status',
            'user',
        ]

    def get_assignments(self, obj):
        try:
            qs = Assignment.objects.filter(reviewer_id=obj.id, parent__isnull=True)
            return AssignmentSerializer(qs, many=True).data
        except Assignment.DoesNotExist:
            return None

    def get_reviewers(self, obj):
        users = []
        reviewers = Reviewer.objects.select_related('document').filter(document_id=obj.document_id)
        for reviewer in reviewers:
            user = reviewer.user
            users.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'father_name': user.father_name,
                'full_name': user.full_name,
                'color': user.color,
                # 'position': user.position.name,
            })
        return users


class ReviewerPerformSerializer(serializers.ModelSerializer):
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name'], read_only=True)
    comment = serializers.CharField(max_length=2000, required=False, allow_null=True, allow_blank=True)
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Reviewer
        fields = [
            'comment',
            'files',
            'modified_date',
            'status',
            'read_time',
            'is_read',
        ]
        read_only_fields = ['modified_date', 'read_time', 'is_read']

    def validate(self, attrs):
        request = self.context.get('request')
        content = attrs.get('comment', None)

        if not content:
            msg = get_response_message(request, 600)
            msg['message'] = msg['message'].format(type='comment')
            raise ValidationError2(msg)

        return attrs

    def update(self, instance, validated_data):
        files = validated_data.pop('files', [])
        instance = super().update(instance, validated_data)
        serialize_m2m('update', File, 'files', files, instance)

        return instance
