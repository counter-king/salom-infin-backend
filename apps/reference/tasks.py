from apps.reference.models import ActionModel, ActionDescription
from config.celery import app
from utils.tools import get_or_none


@app.task(max_retries=1)
def action_log(user_id, action, description_code,
               ct_id, object_id,
               ip=None, new_value=None, old_value=None):
    description = get_or_none(ActionDescription, code=description_code)
    write_action_log(action, user_id, description.id,
                     ct_id, object_id,
                     new_value=new_value,
                     old_value=old_value,
                     ip_addr=ip)


def write_action_log(action: str, user_id: int,
                     description_id: int,
                     ct_id, object_id,
                     old_value=None,
                     new_value=None,
                     ip_addr=None,
                     cause_of_deletion=None):
    ActionModel.objects.create(
        action=action,
        created_by_id=user_id,
        description_id=description_id,
        object_id=object_id,
        old_value=old_value,
        new_value=new_value,
        ip_addr=ip_addr,
        cause_of_deletion=cause_of_deletion,
        content_type_id=ct_id,
    )
