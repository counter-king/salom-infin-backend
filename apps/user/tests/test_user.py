from rest_framework import status


def test_user_registered_or_not(api_client, user, error_messages):
    url = '/api/v1/login/'
    data = {
        'username': 'test',
        'password': 'test2023'
    }
    response = api_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data.get('code') == '703'
    assert response.data.get('message') == 'Account did not register'


def test_user_is_active_or_not(api_client, user, error_messages):
    url = '/api/v1/login/'
    user.is_registered = True
    user.is_user_active = False
    user.save()
    data = {
        'username': 'test',
        'password': 'test2023'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data.get('code') == '702'
    assert response.data.get('message') == 'Account is not active'


def test_user_with_invalid_credentials(api_client, user, error_messages):
    url = '/api/v1/login/'
    user.is_registered = True
    user.save()
    data = {
        'username': 'test',
        'password': 'test2024'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data.get('code') == '701'
    assert response.data.get('message') == 'Login or password is incorrect'


def test_user_with_valid_credentials(api_client, user):
    url = '/api/v1/login/'
    user.is_registered = True
    user.save()
    data = {
        'username': 'test',
        'password': 'test2023'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK


# def test_create_user(api_client, admin_token, company, top_level_department, position, error_messages):
#     url = '/api/v1/users/'
#     data = {
#         "company": company.id,
#         "top_level_department": top_level_department.id,
#         "first_name": "Test",
#         "last_name": "User",
#         "father_name": "Test",
#         "phone": "998001234567",
#         "position": position.id,
#         "department_ids": [top_level_department.id],
#         "tin": "123456789",
#         "birth_date": "1990-01-01",
#         "begin_work_date": "2023-01-01",
#         "pinfl": "12245678901236",
#     }
#     headers = {
#         'Authorization': f'Bearer {admin_token}'
#     }
#
#     response = api_client.post(url, data, headers=headers, format='json')
#     assert response.status_code == status.HTTP_201_CREATED
#     assert response.data.get('first_name') == 'Test'
#     assert response.data.get('last_name') == 'User'
#     assert response.data.get('father_name') == 'Test'
#     # assert response.data.get('phone') == '998001234567'
#     assert response.data.get('position').get('id') == position.id
#     # assert response.data.get('pinfl') == '12245678901236'
#     # assert response.data.get('tin') == '123456789'
#     # assert response.data.get('birth_date') == '1990-01-01'
#     # assert response.data.get('begin_work_date') == '2023-01-01'
#     assert response.data.get('department_ids') == [top_level_department.id]
#     assert response.data.get('company').get('id') == company.id
#     assert response.data.get('top_level_department').get('id') == top_level_department.id
#     # assert response.data.get('username') == response.data.get('phone')


# def test_update_user(api_client, admin_token, user, company, top_level_department, position, error_messages):
#     url = f'/api/v1/users/{user.id}/'
#     data = {
#         "company": company.id,
#         "top_level_department": top_level_department.id,
#         "first_name": "TestUpdated",
#         "last_name": "UserUpdated",
#         "father_name": "TestUpdated",
#         # "phone": "998001234567",
#         "position": position.id,
#         "department_ids": [top_level_department.id],
#         # "tin": "123456789",
#         # "birth_date": "1990-01-01",
#         # "begin_work_date": "2023-01-01"
#     }
#     headers = {
#         'Authorization': f'Bearer {admin_token}'
#     }
#     response = api_client.put(url, data, headers=headers, format='json')
#     assert response.status_code == status.HTTP_200_OK
#     assert response.data.get('first_name') == 'TestUpdated'
#     assert response.data.get('last_name') == 'UserUpdated'
#     assert response.data.get('father_name') == 'TestUpdated'
#     # assert response.data.get('phone') == '998001234567'
#     assert response.data.get('position').get('id') == position.id
#     # assert response.data.get('tin') == '123456789'
#     # assert response.data.get('birth_date') == '1990-01-01'
#     # assert response.data.get('begin_work_date') == '2023-01-01'
#     assert response.data.get('department_ids') == [top_level_department.id]
#     assert response.data.get('company').get('id') == company.id
#     assert response.data.get('top_level_department').get('id') == top_level_department.id
#     # assert response.data.get('username') == 'test'


# def test_updated_user_with_error(api_client, admin_token, user, error_messages):
#     url = f'/api/v1/users/{user.id}/'
#     headers = {
#         'Authorization': f'Bearer {admin_token}'
#     }
#     data = {
#         "username": "admin"
#     }
#     response = api_client.put(url, data, headers=headers, format='json')
#     assert response.status_code == status.HTTP_400_BAD_REQUEST


# def test_create_user_with_error(api_client, admin_token, company, top_level_department, position, error_messages):
#     url = '/api/v1/users/'
#     data = {
#         "company": company.id,
#         "top_level_department": top_level_department.id,
#         "first_name": "Test",
#         "last_name": "User",
#         "father_name": "Test",
#         "phone": "admin",
#         "position": position.id,
#         "department_ids": [top_level_department.id]
#     }
#     headers = {
#         'Authorization': f'Bearer {admin_token}'
#     }
#
#     response = api_client.post(url, data, headers=headers, format='json')
#     print(response.data)
#     assert response.status_code == status.HTTP_400_BAD_REQUEST
#     assert response.data.get('code') == '602'


# def test_send_otp_to_user_and_verify(api_client, user, error_messages):
#     url = '/api/v1/send-otp/'
#     data = {
#         'phone_number': user.phone
#     }
#     response = api_client.post(url, data, format='json')
#     assert response.status_code == status.HTTP_200_OK
#     assert response.data.get('status') == 'success'
#     user.otp = '123456'
#     user.save()
#
#     # Verify OTP
#     url = '/api/v1/verify-phone/'
#     data = {
#         'phone_number': user.phone,
#         'otp_code': user.otp
#     }
#     response = api_client.post(url, data, format='json')
#     assert response.status_code == status.HTTP_200_OK
#     assert response.data.get('status') == 'success'


def test_send_otp_to_not_existed_user(api_client, error_messages):
    url = '/api/v1/send-otp/'
    data = {
        'phone_number': '998771234569'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data.get('code') == '623'
    assert response.data.get('message') == '998771234569 not found'


# def test_send_and_verify_wrong_otp(api_client, user, error_messages):
#     url = '/api/v1/send-otp/'
#     data = {
#         'phone_number': user.phone
#     }
#     response = api_client.post(url, data, format='json')
#     assert response.status_code == status.HTTP_200_OK
#     assert response.data.get('status') == 'success'
#     user.otp = '123456'
#     user.save()
#
#     # Verify OTP
#     url = '/api/v1/verify-phone/'
#     data = {
#         'phone_number': user.phone,
#         'otp_code': '123457'
#     }
#     response = api_client.post(url, data, format='json')
#     assert response.status_code == status.HTTP_404_NOT_FOUND
#     assert response.data.get('code') == '623'


def test_profile_view(api_client, user, user1_token):
    url = '/api/v1/profile/'
    headers = {
        'Authorization': f'Bearer {user1_token}'
    }
    response = api_client.get(url, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.data.get('id') == user.id
    assert response.data.get('first_name') == user.first_name
    assert response.data.get('last_name') == user.last_name
    assert response.data.get('father_name') == user.father_name
    assert response.data.get('phone') == user.phone
    assert response.data.get('username') == user.username
    assert response.data.get('pinfl') == None


def test_change_password(api_client, user, user1_token):
    url = '/api/v1/change-password/'
    headers = {
        'Authorization': f'Bearer {user1_token}'
    }
    data = {
        'old_password': 'test2023',
        'new_password': 'test2024'
    }

    response = api_client.put(url, data, headers=headers, format='json')
    assert response.status_code == status.HTTP_200_OK
