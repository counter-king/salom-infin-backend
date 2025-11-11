def get_compose_status_id(type='default'):
    from apps.compose.models import ComposeStatus

    if type == 'draft':
        return ComposeStatus.objects.get(is_draft=True).id
    elif type == 'done':
        return ComposeStatus.objects.get(is_approve=True).id
    else:
        return ComposeStatus.objects.get(is_default=True).id


def get_default_base_doc_status_id():
    from apps.reference.models import StatusModel
    return StatusModel.objects.get(is_default=True).id


def get_completed_base_doc_status_id():
    from apps.reference.models import StatusModel
    return StatusModel.objects.get(is_done=True).id


def get_in_progress_base_doc_status_id():
    from apps.reference.models import StatusModel
    return StatusModel.objects.get(is_in_progress=True).id


def get_on_hold_base_doc_status_id():
    from apps.reference.models import StatusModel
    return StatusModel.objects.get(is_on_hold=True).id


def user_search_status_ids():
    from apps.user.models import UserStatus
    status_ids = UserStatus.objects.filter(included_in_search=True).values_list('id', flat=True)
    return list(status_ids)


def user_strict_status_ids():
    from apps.user.models import UserStatus
    status_ids = UserStatus.objects.filter(strict_condition=True).values_list('id', flat=True)
    return list(status_ids)


def user_reasonable_status_ids():
    from apps.user.models import UserStatus
    status_ids = UserStatus.objects.filter(is_reasonable=True).values_list('id', flat=True)
    return list(status_ids)
