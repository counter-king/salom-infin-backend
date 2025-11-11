from __future__ import absolute_import, unicode_literals

import logging
import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery(settings.CELERY_APP_NAME, broker=settings.BROKER_URL)

app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.update(
    broker_connection_retry_on_startup=True,
)

# Celery beat settings (Asia/Tashkent)
app.conf.beat_schedule = {
    '2300-build_today_payroll_report': {
        'task': 'apps.hr.tasks.payroll.build_today_payroll_table',
        'schedule': crontab(minute='0', hour='23'),
    },
    '0000-company-sync-branches': {
        'task': 'apps.company.tasks.update_company_branches',
        'schedule': crontab(minute='0', hour='0'),
    },
    '0100-company-sync-positions': {
        'task': 'apps.company.tasks.update_positions',
        'schedule': crontab(minute='0', hour='1'),
    },
    '0130-company-sync-top-level-departments': {
        'task': 'apps.company.tasks.update_top_level_departments',
        'schedule': crontab(minute='30', hour='1'),
    },
    '0200-company-sync-sub-departments': {
        'task': 'apps.company.tasks.update_sub_departments',
        'schedule': crontab(minute='0', hour='2'),
    },
    '0230-company-sync-sub-sub-departments': {
        'task': 'apps.company.tasks.update_sub_sub_departments',
        'schedule': crontab(minute='30', hour='2'),
    },
    '0240-company-sync-department-status': {
        'task': 'apps.company.tasks.update_department_status',
        'schedule': crontab(minute='40', hour='2'),
    },
    '0300-recheck-yesterday-payroll-report': {
        'task': 'apps.hr.tasks.payroll.recheck_yesterday_payroll_table',
        'schedule': crontab(minute='0', hour='3'),
    },
    '0330-yesterday-sync-attendance': {
        'task': 'apps.hr.tasks.sync_daily_attendance.sync_yesterday_attendance',
        'schedule': crontab(minute='30', hour='3'),
    },
    '0400-user-sync-or-create': {
        'task': 'apps.user.tasks.update_or_create_users',
        'schedule': crontab(minute='0', hour='4'),
    },
    '0410-user-sync-from-ldap': {
        'task': 'apps.user.tasks.update_users_from_ldap',
        'schedule': crontab(minute='10', hour='4'),
    },
    '0420-user-save-leave-end-date': {
        'task': 'apps.user.tasks.save_leave_end_date',
        'schedule': crontab(minute='20', hour='4'),
    },
    '0430-user-sync-department': {
        'task': 'apps.user.tasks.update_employees_department',
        'schedule': crontab(minute='30', hour='4'),
    },
    '0440-user-sync-rank': {
        'task': 'apps.user.tasks.update_employee_rank',
        'schedule': crontab(minute='40', hour='4'),
    },
    '0500-yesterday-sync-attendance': {
        'task': 'apps.hr.tasks.sync_daily_attendance.sync_yesterday_attendance',
        'schedule': crontab(minute='0', hour='5'),
    },
    '0520-user-sync-condition': {
        'task': 'apps.user.tasks.update_user_condition',
        'schedule': crontab(minute='20', hour='5'),
    },
    '0600-hr-fetch-payroll-d02': {
        'task': 'apps.hr.tasks.payroll.fetch_payroll_data',
        'schedule': crontab(minute='0', hour='6', day_of_month='2'),
    },
    '1000-user-notify-vacation': {
        'task': 'apps.user.tasks.send_sms_to_users_about_vacation',
        'schedule': crontab(minute='0', hour='10'),
    },
    '1030-user-notify-on-vacation-workday': {
        'task': 'apps.user.tasks.send_sms_to_users_on_vacation',
        'schedule': crontab(minute='0', hour='11'),
    },
    '1120-user-notify-unpaid-leave-workday': {
        'task': 'apps.user.tasks.send_sms_to_users_on_unpaid_leave',
        'schedule': crontab(minute='20', hour='11'),
    },
    '1130-daily-attendance-sync': {
        'task': 'apps.hr.tasks.sync_daily_attendance.sync_daily_attendance',
        'schedule': crontab(minute='30', hour='11'),
    },
}

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(6000.0, periodic_task_from_debug.s(), name='DEBUG TASK')
    # sender.add_periodic_task(1500.0, periodic_task_from_user.s(), name='UPDATE USERNAME TASK')
    # sender.add_periodic_task(6000.0, periodic_task_from_department.s(), name='UPDATE IABS DEPT ID TASK')
    sender.add_periodic_task(3600.0, sync_iabs_calendar_task.s(), name='SYNC IABS CALENDAR TASK')
    sender.add_periodic_task(7200.0, sync_unregistered_attendance.s(), name='SYNC DAILY UNREGISTERED ATTENDANCE')


@app.task(bind=True)
def periodic_task_from_debug(*args, **kwargs):
    from apps.compose.tasks.utils import debug_tasks
    logging.info('test running')
    debug_tasks()


# @app.task
# def periodic_task_from_user(*args, **kwargs):
#     from apps.user.tasks import update_usernames
#     logging.info('updating usernames')
#     update_usernames()


# @app.task
# def periodic_task_from_department(*args, **kwargs):
#     from apps.company.tasks import update_iabs_dep_id
#     logging.info('updating iabs dept id')
#     update_iabs_dep_id()

@app.task
def sync_iabs_calendar_task():
    from apps.hr.tasks.sync_calendar import sync_iabs_calendar
    logging.info('syncing iabs calendar')
    sync_iabs_calendar()


@app.task
def sync_unregistered_attendance():
    from apps.hr.tasks.sync_daily_attendance import sync_daily_unregistered_attendance
    logging.info('syncing daily unregistered attendance')
    sync_daily_unregistered_attendance()
