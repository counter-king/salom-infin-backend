import graphene
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from apps.reference.filters import CorrespondentFilter, EmployeeGroupFilter
from apps.reference.models import (
    Correspondent,
    DeliveryType,
    DocumentType,
    EmployeeGroup,
    Journal,
    LanguageModel,
    Priority,
    ShortDescription,
    StatusModel,
)
from apps.user.models import User


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'is_user_active', 'is_superuser', 'is_staff',
                  'created_date']


class DocumentTypeType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = DocumentType
        fields = ['id', 'name', 'short_name']


class JournalType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Journal
        fields = ['id', 'name']


class PriorityType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Priority
        fields = ['id', 'name']


class DeliveryTypeType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = DeliveryType
        fields = ['id', 'name']


class LanguageModelType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = LanguageModel
        fields = ['id', 'name']


class StatusModelType(DjangoObjectType):
    class Meta:
        model = StatusModel
        fields = ['id', 'name', 'description', 'group', 'is_default', 'created_date']
        # interfaces = (relay.Node,)


class CorrespondentType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = Correspondent
        fields = [
            'address',
            'birth_date',
            'checkpoint',
            'description',
            'email',
            'father_name',
            'first_name',
            'gender',
            'id',
            'last_name',
            'legal_address',
            'legal_name',
            'name',
            'phone',
            'tin',
            'type',
        ]
        interfaces = (relay.Node,)


class EmployeeGroupType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)
    employees = graphene.List(UserType, limit=graphene.Int())

    class Meta:
        model = EmployeeGroup
        fields = ['id', 'name', 'employees', 'created_date']
        interfaces = (relay.Node,)

    def resolve_employees(self, info):
        return self.employees.all()


class ShortDescriptionType(DjangoObjectType):
    id = graphene.ID(source='pk', required=True)

    class Meta:
        model = ShortDescription
        fields = ['id', 'description', 'description_uz', 'description_ru', 'created_date']
        interfaces = (relay.Node,)


# Define a GraphQL query object called Query, which inherits from graphene.ObjectType
class Query(graphene.ObjectType):
    # Define a field called 'status' that returns a list of StatusModelType objects
    status = graphene.List(StatusModelType)
    # Define a field called 'status_by_id' that takes an 'id' argument and returns a single StatusModelType object
    status_by_id = graphene.Field(StatusModelType, id=graphene.Int())
    # Define a field called 'correspondent' that returns a list of CorrespondentType objects
    correspondent = DjangoFilterConnectionField(CorrespondentType, filterset_class=CorrespondentFilter)
    # Define a field called 'correspondent_by_id' that takes an 'id' argument and returns a single CorrespondentType object
    correspondent_by_id = graphene.Field(CorrespondentType, id=graphene.Int())
    # Define a field called 'employee_group' that returns a list of EmployeeGroupType objects
    employee_group = DjangoFilterConnectionField(EmployeeGroupType, filterset_class=EmployeeGroupFilter)
    # Define a field called 'employee_group_by_id' that takes an 'id' argument and returns a single EmployeeGroupType object
    employee_group_by_id = graphene.Field(EmployeeGroupType, id=graphene.Int())
    # Define a field called 'short_description' that returns a list of ShortDescriptionType objects
    short_description = DjangoFilterConnectionField(ShortDescriptionType, search=graphene.String(),
                                                    fields=['description'])
    # Define a field called 'short_description_by_id' that takes an 'id' argument and returns a single ShortDescriptionType object
    short_description_by_id = graphene.Field(ShortDescriptionType, id=graphene.Int())

    # Resolve the 'status' field. This function is executed to fetch all StatusModel objects from the database
    def resolve_status(self, info, **kwargs):
        return StatusModel.objects.all()

    # Resolve the 'status_by_id' field. This function is executed to fetch a single StatusModel object based on the provided 'id'
    def resolve_status_by_id(self, info, id):
        return StatusModel.objects.get(pk=id)

    # Resolve the 'correspondent' field. This function is executed to fetch all Correspondent objects from the database
    def resolve_correspondent(self, info, **kwargs):
        return Correspondent.objects.all()

    # Resolve the 'correspondent_by_id' field. This function is executed to fetch a single Correspondent object based on the provided 'id'
    def resolve_correspondent_by_id(self, info, id):
        return Correspondent.objects.get(pk=id)

    # Resolve the 'employee_group' field. This function is executed to fetch all EmployeeGroup objects from the database
    def resolve_employee_group(self, info, **kwargs):
        return EmployeeGroup.objects.all()

    # Resolve the 'employee_group_by_id' field. This function is executed to fetch a single EmployeeGroup object based on the provided 'id'
    def resolve_employee_group_by_id(self, info, id):
        return EmployeeGroup.objects.get(pk=id)

    # Resolve the 'short_description' field. This function is executed to fetch all ShortDescription objects from the database
    def resolve_short_description(self, info, search=None, **kwargs):
        qs = ShortDescription.objects.all()

        if search:
            filter = (
                    Q(description__icontains=search) |
                    Q(description_ru__icontains=search) |
                    Q(description_uz__icontains=search)
            )
            qs = qs.filter(filter)
        return qs

    # Resolve the 'short_description_by_id' field. This function is executed to fetch a single ShortDescription object based on the provided 'id'
    def resolve_short_description_by_id(self, info, id):
        return ShortDescription.objects.get(pk=id)
