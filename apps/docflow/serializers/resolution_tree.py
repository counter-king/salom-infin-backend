from rest_framework import serializers

from apps.docflow.models import Assignment, Reviewer, BaseDocument, Assignee
from apps.document.serializers import FileSerializer
from utils.serializer import SelectItemField


class RecursiveSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class ResolutionTreePerformerSerializer(serializers.ModelSerializer):
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           read_only=True)
    status = SelectItemField(model="reference.StatusModel", extra_field=['id', 'name'], read_only=False)
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Assignee
        fields = [
            'content',
            'created_date',
            'files',
            'id',
            'is_controller',
            'is_performed',
            'is_read',
            'is_responsible',
            'modified_date',
            'performed_date',
            'read_time',
            'status',
            'user',
        ]


class ResolutionTreeListSerializer(serializers.ModelSerializer):
    assignees = ResolutionTreePerformerSerializer(read_only=True, many=True)
    user = serializers.SerializerMethodField(read_only=True)
    children = RecursiveSerializer(many=True, read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'assignees',
            'children',
            'content',
            'created_date',
            'deadline',
            'id',
            'is_verified',
            'is_project_resolution',
            'modified_by',
            'modified_date',
            'receipt_date',
            'reviewer',
            'type',
            'user',
        ]

    def get_user(self, obj):
        if obj.created_by:
            return obj.created_by.dict()
        return None


class ReviewerTreeSerializer(serializers.ModelSerializer):
    assignments = serializers.SerializerMethodField(read_only=True)
    user = SelectItemField(model="user.User",
                           extra_field=['full_name', 'first_name', 'last_name',
                                        'color', 'id', 'position', 'status', 'cisco', 'avatar',
                                        'top_level_department', 'department', 'company', 'email'],
                           read_only=True)
    status = SelectItemField(model="reference.StatusModel", read_only=True,
                             extra_field=['id', 'name', 'group', 'description'])
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
            'read_time',
            'status',
            'user',
        ]

    def get_assignments(self, obj):
        qs = Assignment.objects.filter(reviewer_id=obj.id, parent__isnull=True)
        if qs.exists():
            serializer = ResolutionTreeListSerializer(qs, many=True)
            return serializer.data
        return []


class ResolutionTreeSerializer(serializers.ModelSerializer):
    reviewers = ReviewerTreeSerializer(many=True, read_only=True)

    class Meta:
        model = BaseDocument
        fields = ['id', 'reviewers']
