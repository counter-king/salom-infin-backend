from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.reference.models import ErrorMessage, ActionDescription
from apps.user.models import User


class ReferenceTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='test',
            password='test2023')
        self.token = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        action_descriptions = [
            {
                'code': '119',
                'description': 'Test description'
            },
            {
                'code': '120',
                'description': 'Test description'
            },
            {
                'code': '121',
                'description': 'Test description'
            },
            {
                'code': '122',
                'description': 'Test description'
            }
        ]

        for action_description in action_descriptions:
            ActionDescription.objects.create(**action_description)

        error_messages = [
            {
                'code': '600',
                'message': '{type} is required',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '601',
                'message': '{req_field} is required when type is {type}',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '602',
                'message': 'This {object} already exists',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '603',
                'message': 'This {object} does not exist',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '604',
                'message': 'You can\'t delete this object because it is connected to other objects',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '700',
                'message': 'You don\'t have permission to perform this action',
                'status': 'fail',
                'status_code': 400
            },
            {
                'code': '801',
                'message': '{object} has been deleted successfully',
                'status': 'fail',
                'status_code': 400
            }
        ]
        for error_message in error_messages:
            ErrorMessage.objects.create(**error_message)

        self.headers = {
            'Accept-Language': 'uz'
        }

    def test_crud_of_status(self):
        url = '/api/v1/status/'

        # Create
        data = {
            'name': 'Jarayonda',
            'name_ru': 'В процессе',
            'name_uz': 'Jarayonda',
            'name_en': 'In Progress',
            'is_default': True,
            'group': 'IN_PROGRESS'
        }
        response = self.client.post(url, data, format='json', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name_uz'), 'Jarayonda')
        self.assertEqual(response.data.get('is_default'), True)
        self.assertEqual(response.data.get('group'), 'IN_PROGRESS')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name_uz'), 'Jarayonda')

        # Update
        data = {
            'name': 'Jarayon',
            'name_ru': 'В процессе',
            'name_uz': 'Jarayonda',
            'name_en': 'In Progress',
            'is_default': True,
            'group': 'IN_PROGRESS',
            'description': 'Test description'
        }
        response = self.client.put(f'{url}{id}/', data, format='json', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name_uz'), 'Jarayonda')
        self.assertEqual(response.data.get('description'), 'Test description')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_correspondent(self):
        url = '/api/v1/correspondents/'

        # Create
        data = {
            'name': 'Test Organization',
            'legal_name': 'Test Organization',
            'tin': '123456789',
            'address': 'Test address',
            'phone': '+998 99 999 99 99',
            'legal_address': 'Test legal address'
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('message'), 'type is required')

        data['type'] = 'legal'
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test Organization')
        self.assertEqual(response.data.get('legal_name'), 'Test Organization')
        self.assertEqual(response.data.get('type'), 'legal')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Organization')
        self.assertNotEqual(response.data.get('name'), 'Test Organization 2')
        self.assertNotEqual(response.data.get('legal_name'), 'Test Organization 2')
        self.assertNotEqual(response.data.get('tin'), '1234567890')

        # Update
        data = {
            'name': 'Test Organization 2',
            'legal_name': 'Test Organization 2',
            'tin': '1234567890',
            'address': 'Test address',
            'phone': '+998 99 999 99 99',
            'legal_address': 'Test legal address',
            'type': 'legal'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Organization 2')
        self.assertEqual(response.data.get('legal_name'), 'Test Organization 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # physical correspondent
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'father_name': 'Doe',
            'address': 'Test address',
            'phone': '+998 99 999 99 99',
            'type': 'physical'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotEqual(response.data.get('message'), 'gender is required')

        data['gender'] = 'm'
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('first_name'), 'John')
        self.assertEqual(response.data.get('last_name'), 'Doe')
        self.assertEqual(response.data.get('father_name'), 'Doe')
        self.assertEqual(response.data.get('address'), 'Test address')
        self.assertNotEqual(response.data.get('address'), 'Test address 2')
        self.assertNotEqual(response.data.get('type'), 'legal')
        self.assertEqual(response.data.get('type'), 'physical')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('first_name'), 'John')
        self.assertEqual(response.data.get('last_name'), 'Doe')
        self.assertEqual(response.data.get('father_name'), 'Doe')
        self.assertEqual(response.data.get('address'), 'Test address')
        self.assertNotEqual(response.data.get('address'), 'Test address 2')

        # Update
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'father_name': 'Doe',
            'address': 'Updated test address 2',
            'phone': '+998 99 999 99 10',
            'type': 'physical',
            'gender': 'm'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('address'), 'Updated test address 2')
        self.assertNotEqual(response.data.get('address'), 'Test address 2')
        self.assertNotEqual(response.data.get('phone'), '+998 99 999 99 99')
        self.assertEqual(response.data.get('phone'), '+998 99 999 99 10')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_employee_group(self):
        url = '/api/v1/employee-groups/'

        # Create
        data = {
            'name': 'Test Employee Group',
            'employees': [{'id': self.admin.id}]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test Employee Group')
        self.assertEqual(response.data.get('employees')[0].get('id'), self.admin.id)

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Employee Group')

        # Update
        data = {
            'name': 'Test Employee Group 2',
            'employees': []
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Employee Group 2')
        self.assertEqual(response.data.get('employees'), [])

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_short_description(self):
        url = '/api/v1/short-descriptions/'

        # Create
        data = {
            'description': 'Test Description',
            'description_ru': 'Test Description RU',
            'description_uz': 'Test Description UZ',
            'description_en': 'Test Description EN'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('description_uz'), 'Test Description UZ')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('description_uz'), 'Test Description UZ')

        # Update
        data = {
            'description': 'Test Description 2',
            'description_ru': 'Test Description RU 2',
            'description_uz': 'Test Description UZ 2',
            'description_en': 'Test Description EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('description_uz'), 'Test Description UZ 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_journal(self):
        url = '/api/v1/journals/'

        # Create
        data = {
            'index': 'Test Index',
            'is_active': True,
            'is_auto_numbered': False,
            'name': 'Test Journal',
            'name_ru': 'Test Journal RU',
            'name_uz': 'Test Journal UZ',
            'name_en': 'Test Journal EN'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('index'), 'Test Index')
        self.assertEqual(response.data.get('name_uz'), 'Test Journal UZ')
        self.assertEqual(response.data.get('is_active'), True)
        self.assertEqual(response.data.get('is_auto_numbered'), False)

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('index'), 'Test Index')
        self.assertEqual(response.data.get('name_uz'), 'Test Journal UZ')
        self.assertEqual(response.data.get('is_active'), True)
        self.assertEqual(response.data.get('is_auto_numbered'), False)

        # Update
        data = {
            'index': '23',
            'is_auto_numbered': True,
            'name': 'Test Journal 2',
            'name_ru': 'Test Journal RU 2',
            'name_uz': 'Test Journal UZ 2',
            'name_en': 'Test Journal EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('index'), '23')
        self.assertEqual(response.data.get('name_uz'), 'Test Journal UZ 2')
        self.assertEqual(response.data.get('is_auto_numbered'), True)

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_document_type(self):
        url = '/api/v1/document-types/'

        # Create
        data = {
            'name': 'Test Document Type',
            'name_ru': 'Test Document Type RU',
            'name_uz': 'Test Document Type UZ',
            'name_en': 'Test Document Type EN',
            'short_name': 'Test Short Name'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name_uz'), 'Test Document Type UZ')
        self.assertEqual(response.data.get('short_name'), 'Test Short Name')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name_uz'), 'Test Document Type UZ')
        self.assertEqual(response.data.get('short_name'), 'Test Short Name')

        # Update
        data = {
            'name': 'Test Document Type 2',
            'name_ru': 'Test Document Type RU 2',
            'name_uz': 'Test Document Type UZ 2',
            'name_en': 'Test Document Type EN 2',
            'short_name': 'Test Short Name 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name_uz'), 'Test Document Type UZ 2')
        self.assertEqual(response.data.get('short_name'), 'Test Short Name 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_language(self):
        url = '/api/v1/languages/'

        # Create
        data = {
            'name': 'Uzbek',
            'name_ru': 'Test Language RU',
            'name_uz': 'Test Language UZ',
            'name_en': 'Test Language EN',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Uzbek')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Uzbek')

        # Update
        data = {
            'name': 'Test Language 2',
            'name_ru': 'Test Language RU 2',
            'name_uz': 'Test Language UZ 2',
            'name_en': 'Test Language EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Language 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_region_district(self):
        url = '/api/v1/regions/'

        # Create
        data = {
            'name': 'Test Region',
            'name_ru': 'Test Region RU',
            'name_uz': 'Test Region UZ',
            'name_en': 'Test Region EN'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test Region')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Region')

        # Update
        data = {
            'name': 'Test Region 2',
            'name_ru': 'Test Region RU 2',
            'name_uz': 'Test Region UZ 2',
            'name_en': 'Test Region EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Region 2')

        # Create District
        url = '/api/v1/districts/'
        data = {
            'name': 'Test District',
            'name_ru': 'Test District RU',
            'name_uz': 'Test District UZ',
            'name_en': 'Test District EN',
            'region': id
        }
        district_id = response.data.get('id')
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test District')
        self.assertEqual(response.data.get('id'), district_id)
        self.assertEqual(response.data.get('region').get('id'), id)

        # Try to delete region and get error
        response = self.client.delete(f'/api/v1/regions/{id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('message'),
                         "You can't delete this object because it is connected to other objects")

        # Retrieve District
        response = self.client.get(f'{url}{district_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test District')

        # Update District
        data = {
            'name': 'Test District 2',
            'name_ru': 'Test District RU 2',
            'name_uz': 'Test District UZ 2',
            'name_en': 'Test District EN 2',
            'region': id
        }
        response = self.client.put(f'{url}{district_id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test District 2')

        # Delete District
        response = self.client.delete(f'{url}{district_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Delete Region
        response = self.client.delete(f'/api/v1/regions/{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_delivery_type(self):
        url = '/api/v1/delivery-types/'

        # Create
        data = {
            'name': 'Test Delivery Type',
            'name_ru': 'Test Delivery Type RU',
            'name_uz': 'Test Delivery Type UZ',
            'name_en': 'Test Delivery Type EN'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test Delivery Type')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Delivery Type')

        # Update
        data = {
            'name': 'Test Delivery Type 2',
            'name_ru': 'Test Delivery Type RU 2',
            'name_uz': 'Test Delivery Type UZ 2',
            'name_en': 'Test Delivery Type EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Delivery Type 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_priority(self):
        url = '/api/v1/priorities/'

        # Create
        data = {
            'name': 'Test Priority',
            'name_ru': 'Test Priority RU',
            'name_uz': 'Test Priority UZ'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), 'Test Priority')

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Priority')

        # Update
        data = {
            'name': 'Test Priority 2',
            'name_ru': 'Test Priority RU 2',
            'name_uz': 'Test Priority UZ 2',
            'name_en': 'Test Priority EN 2'
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Test Priority 2')

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_crud_of_comments(self):
        url = '/api/v1/comments/'

        # Create
        data = {
            'description': 'Test Comment',
            'object_id': 1
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('description'), 'Test Comment')
        self.assertEqual(response.data.get('object_id'), 1)

        # Retrieve
        id = response.data.get('id')
        response = self.client.get(f'{url}{id}/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('description'), 'Test Comment')
        self.assertEqual(response.data.get('object_id'), 1)

        # Update
        data = {
            'description': 'Test Comment 2',
            'object_id': 1
        }
        response = self.client.put(f'{url}{id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('description'), 'Test Comment 2')
        self.assertEqual(response.data.get('object_id'), 1)
        self.assertEqual(response.data.get('is_edited'), True)

        # Delete
        response = self.client.delete(f'{url}{id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
