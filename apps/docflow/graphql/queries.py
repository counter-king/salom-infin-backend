import graphene
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from apps.docflow.filters import DocFlowFilters, ReviewerFilters, AssignmentFilters
from apps.docflow.models import BaseDocument, Reviewer, Assignment, Assignee
from apps.reference.graphql.queries import DocumentTypeType, JournalType, LanguageModelType, PriorityType


class BaseDocumentType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)
    document_type = graphene.Field(DocumentTypeType)
    journal = graphene.Field(JournalType)
    language = graphene.Field(LanguageModelType)
    priority = graphene.Field(PriorityType)

    class Meta:
        model = BaseDocument
        fields = [
            'code',
            'correspondent',
            'delivery_type',
            'description',
            'document_type',
            'grif',
            'id',
            'journal',
            'language',
            'outgoing_date',
            'outgoing_number',
            'priority',
            'register_date',
            'register_number',
            'status',
            'title',
        ]
        interfaces = (relay.Node,)


class ReviewerType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Reviewer
        fields = [
            'document',
            'has_resolution',
            'id',
            'is_read',
            'read_time',
            'status',
            'user',
        ]
        interfaces = (relay.Node,)


class AssigneeType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Assignee
        fields = [
            'assignment',
            'is_controller',
            'id',
            'is_read',
            'read_time',
            'status',
            'user',
            'is_performed',
            'performed_date',
            'is_responsible',
        ]
        interfaces = (relay.Node,)


class AssignmentType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)
    assignees = graphene.List(AssigneeType)

    class Meta:
        model = Assignment
        fields = [
            'assignees',
            'content',
            'deadline',
            'has_child_resolution',
            'id',
            'is_project_resolution',
            'receipt_date',
            'reviewer',
            'type',
            'is_verified',
            'parent',
        ]
        interfaces = (relay.Node,)

    def resolve_assignees(self, info, **kwargs):
        return self.assignees.all()


class Query(graphene.ObjectType):
    document = DjangoFilterConnectionField(BaseDocumentType, filterset_class=DocFlowFilters)
    reviewer = DjangoFilterConnectionField(ReviewerType, filterset_class=ReviewerFilters)
    assignment = DjangoFilterConnectionField(AssignmentType, filterset_class=AssignmentFilters)
    performers = graphene.List(AssigneeType, assignment_id=graphene.Int())

    def resolve_document(self, info, **kwargs):
        return BaseDocument.objects.all()

    def resolve_reviewer(self, info, **kwargs):
        user_id = info.context.user.id
        return Reviewer.objects.filter(Q(user_id=user_id) | Q(user__assistants__assistant_id=user_id))

    def resolve_assignment(self, info, **kwargs):
        return Assignment.objects.all()

    def resolve_performers(self, info, assignment_id):
        return Assignee.objects.filter(assignment_id=assignment_id)
