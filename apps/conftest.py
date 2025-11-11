import json

import pytest
from rest_framework.test import APIClient

from apps.user.models import User, UserStatus
from apps.company.models import Company, Department, Position
from apps.reference.models import (
    ActionDescription,
    Correspondent,
    DeliveryType,
    District,
    DocumentSubType,
    DocumentType,
    ErrorMessage,
    FieldActionMapping,
    Journal,
    LanguageModel,
    Priority,
    Region,
    StatusModel,
)
from apps.docflow.models import BaseDocument, Reviewer, Assignment, Assignee


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_status():
    return UserStatus.objects.create(
        code='A',
        name='Active',
        code_type='A',
        included_in_search=True,
        strict_condition=True
    )


@pytest.fixture
def user(user_status):
    user1 = User.objects.create_user(
        username='test',
        password='test2023'
    )
    user1.pinfl = '12345678901234'
    user1.phone = '998901234567'
    user1.first_name = 'Test'
    user1.last_name = 'User'
    user1.status_id = user_status.id
    user1.save()

    return user1


@pytest.fixture
def user2(user_status):
    user2 = User.objects.create_user(
        username='test2',
        password='test2023'
    )
    user2.pinfl = '12345678901235'
    user2.phone = '998901234568'
    user2.status_id = user_status.id
    user2.save()

    return user2


@pytest.fixture
def admin_user(user_status):
    admin_user = User.objects.create_superuser(
        username='admin',
        password='admin2023'
    )
    admin_user.pinfl = '12345678901236'
    admin_user.phone = '998901234569'
    admin_user.status_id = user_status.id
    admin_user.save()

    return admin_user


@pytest.fixture
def admin_token(admin_user):
    token = admin_user.tokens

    return token['access']


@pytest.fixture
def user1_token(user):
    token = user.tokens

    return token['access']


@pytest.fixture
def user2_token(user2):
    token = user2.tokens

    return token['access']


@pytest.fixture
def company():
    return Company.objects.create(name='Test Company')


@pytest.fixture
def top_level_department(company):
    return Department.objects.create(name='Top Level Department', company=company)


@pytest.fixture
def department(company, top_level_department):
    return Department.objects.create(name='Department', company=company, parent=top_level_department)


@pytest.fixture
def position():
    return Position.objects.create(name='CEO', code='100')


@pytest.fixture
def document_type():
    return DocumentType.objects.create(
        name='DocumentType',
        short_name='DT'
    )


@pytest.fixture
def document_sub_type(document_type):
    return DocumentSubType.objects.create(
        name='DocumentSubType',
        short_name='DST',
        document_type=document_type
    )


@pytest.fixture
def region():
    return Region.objects.create(
        code='Region',
        name='Region'
    )


@pytest.fixture
def district(region):
    return District.objects.create(
        code='District',
        region=region,
        name='District'
    )


@pytest.fixture
def language():
    return LanguageModel.objects.create(
        name='Language'
    )


@pytest.fixture
def delivery_type():
    return DeliveryType.objects.create(
        name='DeliveryType'
    )


@pytest.fixture
def high_priority():
    return Priority.objects.create(
        name='High'
    )


@pytest.fixture
def low_priority():
    return Priority.objects.create(
        name='Low'
    )


@pytest.fixture
def correspondent():
    return Correspondent.objects.create(
        name='Correspondent',
        legal_name='C',
        type='physical'
    )


@pytest.fixture
def journal():
    return Journal.objects.create(
        name='Journal'
    )


@pytest.fixture
def todo_status():
    # global status for projects
    return StatusModel.objects.create(
        name='To Do', is_default=True
    )


@pytest.fixture
def in_progress_status():
    # global status for projects
    return StatusModel.objects.create(
        name='In Progress', is_in_progress=True
    )


@pytest.fixture
def on_hold_status():
    # global status for projects
    return StatusModel.objects.create(
        name='On Hold', is_on_hold=True
    )


@pytest.fixture
def done_status():
    # global status for projects
    return StatusModel.objects.create(
        name='Done', is_done=True
    )


@pytest.fixture
def error_messages():
    # Read the error messages JSON file
    with open('json_files/error_messages.json', 'r') as file:
        error_messages = file.read()

    # Create the error messages
    for error_message in json.loads(error_messages):
        fields = error_message['fields']
        ErrorMessage.objects.create(
            code=fields['code'],
            message=fields['message'],
            message_ru=fields['message_ru'],
            message_uz=fields['message_uz'],
            status=fields['status'],
            status_code=fields['status_code']
        )


@pytest.fixture
def action_descriptions():
    # Read the action descriptions JSON file
    with open('json_files/action_text.json', 'r') as file:
        action_descriptions = file.read()

    # Create the action descriptions
    for action_description in json.loads(action_descriptions):
        fields = action_description['fields']
        ActionDescription.objects.create(
            description=fields['description'],
            code=fields['code'],
            color=fields['color'],
            icon_name=fields['icon_name']
        )


@pytest.fixture
def field_action_mappings():
    # Read the field action mappings JSON file
    with open('json_files/field_mapping.json', 'r') as file:
        field_action_mappings = file.read()

    # Create the field action mappings
    for field_action_mapping in json.loads(field_action_mappings):
        fields = field_action_mapping['fields']
        FieldActionMapping.objects.create(
            field_name=fields['field_name'],
            action_code=fields['action_code']
        )


@pytest.fixture
def base_document(correspondent, delivery_type, document_type, journal, language, company, todo_status):
    return BaseDocument.objects.create(
        correspondent=correspondent,
        delivery_type=delivery_type,
        document_type=document_type,
        journal=journal,
        language=language,
        title='BaseDocument',
        description='BaseDocument Description',
        code='BD',
        register_date='2023-01-01',
        register_number='BD-01',
        outgoing_number='BD-02',
        outgoing_date='2023-01-02',
        number_of_papers=1,
        company=company,
        status=todo_status
    )


@pytest.fixture
def reviewer(base_document, user, todo_status):
    return Reviewer.objects.create(
        document=base_document,
        user=user,
        comment='Reviewer Comment',
        status=todo_status,
    )
