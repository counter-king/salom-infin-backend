import graphene

from apps.reference.graphql.inputs import CorrespondentInput
from apps.reference.graphql.queries import ShortDescriptionType, CorrespondentType, EmployeeGroupType
from apps.reference.models import ShortDescription, Correspondent, EmployeeGroup
from apps.user.models import User
from utils.decorators import superuser_required


class CreateShortDescriptionInput(graphene.Mutation):
    class Arguments:
        description = graphene.String(required=True)
        description_uz = graphene.String(required=True)
        description_ru = graphene.String(required=False)

    # Class attributes define the response of the mutation
    short_description = graphene.Field(ShortDescriptionType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, description, description_uz, description_ru=None):
        short_description = ShortDescription(description=description, description_ru=description_ru,
                                             description_uz=description_uz)
        short_description.save()
        return CreateShortDescriptionInput(short_description=short_description)


class UpdateShortDescription(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        description = graphene.String(required=True)
        description_uz = graphene.String(required=True)
        description_ru = graphene.String(required=False)

    # Class attributes define the response of the mutation
    short_description = graphene.Field(ShortDescriptionType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id, description, description_uz, description_ru=None):
        short_description = ShortDescription.objects.get(pk=id)
        short_description.description = description
        short_description.description_ru = description_ru
        short_description.description_uz = description_uz
        short_description.save()
        return UpdateShortDescription(short_description=short_description)


class ShortDescriptionDelete(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True, description='ID of the short description to delete')

    # Class attributes define the response of the mutation
    short_description = graphene.Field(ShortDescriptionType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id):
        if not id.strip():
            raise ValueError("ID field cannot be blank.")

        short_description = ShortDescription.objects.get(pk=id)
        short_description.delete()
        return ShortDescriptionDelete(short_description=short_description)


class CreateCorrespondent(graphene.Mutation):
    class Arguments:
        input = CorrespondentInput(required=True)

    # Class attributes define the response of the mutation
    correspondent = graphene.Field(CorrespondentType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, input):
        input.validate(input)  # Validate the input data
        correspondent = Correspondent(**input)
        correspondent.save()
        return CreateCorrespondent(correspondent=correspondent)


class UpdateCorrespondent(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = CorrespondentInput(required=True)

    # Class attributes define the response of the mutation
    correspondent = graphene.Field(CorrespondentType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id, input):
        input.validate(input)
        correspondent = Correspondent.objects.get(pk=id)  # Retrieve the instance
        for attr, value in input.items():
            setattr(correspondent, attr, value)
        correspondent.save()  # Save the updated instance
        return UpdateCorrespondent(correspondent=correspondent)


class DeleteCorrespondent(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    # Class attributes define the response of the mutation
    correspondent = graphene.Field(CorrespondentType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id):
        if not id.strip():
            raise ValueError("ID field cannot be blank.")

        correspondent = Correspondent.objects.get(pk=id)
        correspondent.delete()
        return DeleteCorrespondent(correspondent=correspondent)


class CreateEmployeeGroup(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        employees = graphene.List(graphene.ID, required=True)

    # Class attributes define the response of the mutation
    employee_group = graphene.Field(EmployeeGroupType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, name, employees=None):
        employee_group = EmployeeGroup(name=name)
        employee_group.save()
        if employees:
            for employee_id in employees:
                employee = User.objects.get(pk=employee_id)
                employee_group.employees.add(employee)
        return CreateEmployeeGroup(employee_group=employee_group)


class UpdateEmployeeGroup(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        employees = graphene.List(graphene.ID, required=True)

    # Class attributes define the response of the mutation
    employee_group = graphene.Field(EmployeeGroupType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id, name, employees=None):
        employee_group = EmployeeGroup.objects.get(pk=id)
        employee_group.name = name
        employee_group.save()
        if employees:
            employee_group.employees.clear()
            for employee_id in employees:
                employee = User.objects.get(pk=employee_id)
                employee_group.employees.add(employee)
        return UpdateEmployeeGroup(employee_group=employee_group)


class DeleteEmployeeGroup(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    # Class attributes define the response of the mutation
    employee_group = graphene.Field(EmployeeGroupType)

    @classmethod
    @superuser_required
    def mutate(cls, root, info, id):
        if not id.strip():
            raise ValueError("ID field cannot be blank.")

        employee_group = EmployeeGroup.objects.get(pk=id)
        employee_group.delete()
        return DeleteEmployeeGroup(employee_group=employee_group)


class Mutation(graphene.ObjectType):
    create_short_description = CreateShortDescriptionInput.Field()
    update_short_description = UpdateShortDescription.Field()
    delete_short_description = ShortDescriptionDelete.Field()
    create_correspondent = CreateCorrespondent.Field()
    update_correspondent = UpdateCorrespondent.Field()
    delete_correspondent = DeleteCorrespondent.Field()
    create_employee_group = CreateEmployeeGroup.Field()
    update_employee_group = UpdateEmployeeGroup.Field()
    delete_employee_group = DeleteEmployeeGroup.Field()
