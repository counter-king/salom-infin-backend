from rest_framework import status


def test_base_document(api_client, correspondent, delivery_type, document_type,
                       journal, language, low_priority, region,
                       district, todo_status, company, user, user2, user1_token,
                       error_messages, field_action_mappings, action_descriptions):
    # create base document
    url = '/api/v1/docflow/321/'
    headers = {
        'Authorization': f'Bearer {user1_token}'
    }
    data = {
        'correspondent': correspondent.id,
        'delivery_type': delivery_type.id,
        'document_type': document_type.id,
        'journal': journal.id,
        'language': language.id,
        'priority': low_priority.id,
        'title': 'Test title',
        'description': 'Test description',
        'status': todo_status.id,
        'code': '123',
        'grif': 'Test grif',
        'register_date': '2021-01-01',
        'register_number': '123',
        'outgoing_number': '123',
        'outgoing_date': '2021-01-01',
        'number_of_papers': 1,
        'company': company.id,
        'reviewers': [{'user': user.id}, {'user': user2.id}],
    }

    response = api_client.post(url, data, headers=headers, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data.get('correspondent').get('id') == correspondent.id
    assert response.data.get('delivery_type').get('id') == delivery_type.id
    assert response.data.get('document_type').get('id') == document_type.id
    assert response.data.get('journal').get('id') == journal.id
    assert response.data.get('language').get('id') == language.id
    assert response.data.get('priority').get('id') == low_priority.id
    assert response.data.get('title') == 'Test title'
    assert response.data.get('description') == 'Test description'
    assert response.data.get('status').get('id') == todo_status.id
    assert response.data.get('code') == '123'
    assert response.data.get('grif') == 'Test grif'
    assert response.data.get('register_date') == '2021-01-01'
    assert response.data.get('register_number') == '123'
    assert response.data.get('outgoing_number') == '123'
    assert response.data.get('outgoing_date') == '2021-01-01'
    assert response.data.get('number_of_papers') == 1
    assert response.data.get('company') == company.id


# def test_update_base_document(api_client, user, user1_token, error_messages, field_action_mappings,
#                               action_descriptions, base_document, todo_status, high_priority):
#     url = f'/api/v1/docflow/321/{base_document.id}/'
#     headers = {
#         'Authorization': f'Bearer {user1_token}'
#     }
#     data = {
#         'journal': base_document.journal.id,
#         'priority': high_priority.id,
#         'document_type': base_document.document_type.id,
#         'title': 'Test title updated',
#         'description': 'Test description updated',
#         'code': '123 updated',
#         'grif': 'Test grif updated',
#         'register_date': '2021-01-01',
#         'register_number': '123 updated',
#         'outgoing_number': '123 updated',
#         'outgoing_date': '2021-01-01',
#         'number_of_papers': 1
#     }
#     response = api_client.put(url, data, headers=headers, format='json')
#     print(response.data)
#     assert response.status_code == status.HTTP_200_OK
#     assert response.data.get('correspondent').get('id') == base_document.correspondent.id
#     assert response.data.get('delivery_type').get('id') == base_document.delivery_type.id
#     assert response.data.get('document_type').get('id') == base_document.document_type.id
#     assert response.data.get('journal').get('id') == base_document.journal.id
#     assert response.data.get('language').get('id') == base_document.language.id
#     assert response.data.get('priority').get('id') == todo_status.id
#     assert response.data.get('title') == 'Test title updated'
#     assert response.data.get('description') == 'Test description updated'
#     assert response.data.get('status').get('id') == base_document.status.id
#     assert response.data.get('code') == '123 updated'
#     assert response.data.get('grif') == 'Test grif updated'
#     assert response.data.get('register_date') == '2021-01-01'
#     assert response.data.get('register_number') == '123 updated'
#     assert response.data.get('outgoing_number') == '123 updated'
#     assert response.data.get('outgoing_date') == '2021-01-01'
#     assert response.data.get('number_of_papers') == 1
#     assert response.data.get('company') == base_document.company.id


def test_get_reviewers(api_client, reviewer, user, user1_token, base_document):
    url = f'/api/v1/for-review/321/'
    headers = {
        'Authorization': f'Bearer {user1_token}'
    }

    response = api_client.get(url, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.data.get('count') == 1
    assert response.data.get('results')[0].get('document').get('id') == base_document.id
    assert response.data.get('results')[0].get('user').get('id') == user.id
    assert response.data.get('results')[0].get('status').get('id') == reviewer.status.id
    assert response.data.get('results')[0].get('comment') == reviewer.comment
    assert response.data.get('results')[0].get('has_resolution') == reviewer.has_resolution
    assert response.data.get('results')[0].get('is_read') == reviewer.is_read
    assert response.data.get('results')[0].get('read_time') == reviewer.read_time
    assert response.data.get('results')[0].get('files') == None


def test_change_review_status_and_acquaint(api_client, reviewer, user, user1_token, base_document,
                                           in_progress_status, error_messages, action_descriptions):
    # change review status
    url = f'/api/v1/for-review/321/{reviewer.id}/'
    headers = {
        'Authorization': f'Bearer {user1_token}'
    }
    data = {
        'status': in_progress_status.id
    }
    response = api_client.put(url, data, headers=headers, format='json')
    assert response.status_code == status.HTTP_200_OK
    # status not changed because status is read only
    assert response.data.get('status').get('id') == reviewer.status.id

    # acquaint url
    url = f'/api/v1/for-review/321/{reviewer.id}/acquaint/'
    response = api_client.put(url, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.data.get('id') == reviewer.id
    assert response.data.get('is_read') == True
    assert response.data.get('read_time') != None
    assert response.data.get('type') == 'review_document_acquainted'
