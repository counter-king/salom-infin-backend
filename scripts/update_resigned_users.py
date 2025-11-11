from django.utils import timezone
from apps.user.models import User


def run():
    status_ids = (10, 11, 12, 23, 24, 25)
    users = User.objects.filter(status_id__in=status_ids)
    update_user_count = 0
    update_pinfl_count = 0
    for user in users:
        if user.pinfl and user.pinfl[0] != 'P':
            user.pinfl = f'P{user.pinfl}'
            update_pinfl_count += 1

        now = timezone.now()
        timestamp = int(now.timestamp())

        if user.username and len(user.username) <= 13:
            user.username = f'{user.username}_{timestamp}'

        if user.phone and len(user.phone) <= 13:
            user.phone = f'{user.phone}_{timestamp}'
        user.is_user_active = False
        user.save()
        update_user_count += 1

    print(f'Updated {update_user_count} users')
    print(f'Updated {update_pinfl_count} PINFLs')
