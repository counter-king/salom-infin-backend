import os
import re
import string
import uuid
from datetime import date, datetime
from typing import Union, Type, Tuple, Dict

import django_filters
import requests
from AesEverywhere import aes256
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.utils import timezone

from apps.core.models import SQLQuery
from apps.hr.models import IABSCalendar
from apps.user.models import User
from utils.exception import get_response_message, ValidationError2

SECRET_KEY = os.getenv('DECRYPT_ENCRYPT_KEY')


def get_user_ip(request):
    x_forwarded_for = None
    if request.META:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_or_none(model, request=None, with_none=False, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.MultipleObjectsReturned:
        pass
    except model.DoesNotExist:
        first_value = next(iter(kwargs.values()), None)
        if request:
            message = get_response_message(request, 603)
            message['message'] = message['message'].format(pk=first_value, model=model.__name__)
            raise ValidationError2(message)
        elif with_none:
            return None
        else:
            msg = {
                'message': 'Object does not exist',
                'status': 'fail',
                'status_code': 404,
                'code': 404
            }
            raise ValidationError2(msg)


def get_parents(model, id, parents_list=None):
    if parents_list is None:
        parents_list = []
    node = get_or_none(model, id=id)
    if (node.parent is not None):
        parents_list.append(node.parent.id)
        get_parents(model, node.parent.id, parents_list)

    if node.id not in parents_list:
        parents_list.append(node.id)
    return parents_list


def get_children(model, id):
    """
    Get all descendants of a given model instance using a breadth-first search.

    Args:
        model: The model class to query.
        id: The ID of the parent instance.

    Returns:
        A list of IDs representing all descendant instances.
    """
    try:
        # Ensure the root category exists
        category = model.objects.get(id=id)
    except model.DoesNotExist:
        return []  # Return an empty list if the category does not exist

    descendant_ids = []
    queue = list(category.children.all())  # Fetch direct children
    while queue:
        current = queue.pop(0)
        descendant_ids.append(current.id)
        queue.extend(current.children.all())  # Add current department's children to the queue

    return descendant_ids


class StartDateFilter(django_filters.Filter):
    def filter(self, qs, value):
        if value is not None:
            return qs.filter(**{'%s__date__%s' % (self.field_name, self.lookup_expr): value})
        return qs


class EndDateFilter(django_filters.Filter):
    def filter(self, qs, value):
        if value is not None:
            return qs.filter(**{'%s__date__%s' % (self.field_name, self.lookup_expr): value})
        return qs


class VerifiedFilter(django_filters.Filter):
    def filter(self, qs, value):
        if value is not None:
            if value in (
                    'true', 'True', 1, '1', True, 'verified', 'Verified', 'VERIFIED', 'yes', 'Yes', 'YES', 'y', 'Y',
                    'approved',
                    'Approved', 'APPROVED'):
                return qs.filter(**{'%s' % (self.field_name,): True})
            elif value in (
                    'false', 'False', 0, '0', False, 'not_verified', 'Not Verified', 'NOT VERIFIED', 'no', 'No', 'NO',
                    'n', 'N',
                    'not_approved', 'Not Approved', 'NOT APPROVED'):
                return qs.filter(**{'%s' % (self.field_name,): False})
            elif value in ('none', 'None', 'NONE', 'null', 'Null', 'NULL'):
                return qs.filter(**{'%s' % (self.field_name,): None})

        return qs


class IntegerListFilter(django_filters.Filter):
    def filter(self, qs, value):
        if value not in (None, ''):
            integers = [int(v) for v in value.split(',')]
            return qs.filter(**{'%s__%s' % (self.field_name, self.lookup_expr): integers})
        return qs


class StringListFilter(django_filters.Filter):
    def filter(self, qs, value):
        if value not in (None, ''):
            strings = value.split(',')
            return qs.filter(**{'%s__in' % self.field_name: strings})
        return qs


def remove_all_whitespaces(text: str) -> str:
    return text.translate({ord(c): None for c in string.whitespace}).lower()


def clean_html(raw_html):
    clean = re.compile('<.*?>')
    clean_text = re.sub(clean, '', raw_html)
    return clean_text


def normalize_user_name(name: str) -> str:
    l = name.split()

    if len(l) >= 2:
        first_name = first_letter(l[1])
        return f'{first_name}. {l[0]}'
    else:
        return name


def decrypted_text(text: str) -> str:
    decrypted_text = aes256.decrypt(text, SECRET_KEY)
    decrypted_text = str(decrypted_text, 'utf-8')
    return str(decrypted_text)


def encrypt(text: str) -> str:
    encrypted_text = aes256.encrypt(text, SECRET_KEY)
    return encrypted_text


def send_sms_to_phone(phone, text):
    ENV = os.getenv('ENVIRONMENT')
    API = os.getenv('API_URL_FOR_FILE')
    if ENV == 'DEV':
        url = f"{API}/api/v1/mock-post"  # Mock URL for local development
    else:
        url = os.getenv('PLAY_MOBILE_URL')

    username = os.getenv('PLAY_MOBILE_USER')
    password = os.getenv('PLAY_MOBILE_PASSWORD')

    data = {
        "messages": [
            {
                "recipient": phone,
                "message-id": str(uuid.uuid4()),
                "sms": {
                    "originator": "2500",
                    "content": {
                        "text": text
                    }
                }
            }
        ]
    }

    try:
        if ENV == 'DEV':
            response = requests.post(url, json=data)
        else:
            response = requests.post(url, json=data, auth=(username, password))
            response.raise_for_status()  # Raises an error for bad status codes
        return True, response
    except requests.exceptions.HTTPError as err:
        return False, f"HTTP error occurred: {err}"
    except Exception as err:
        return False, f"Other error occurred: {err}"


def first_letter(name: str) -> str:
    if name is None:
        return ''

    if len(name) == 0:
        return ''

    if name.startswith("Sh"):
        return name[:2]
    elif name.startswith("O'"):
        return name[:2]
    elif name.startswith("G'"):
        return name[:2]
    elif name.startswith("Ch"):
        return name[:2]
    elif name.startswith("Dj"):
        return name[:2]
    else:
        return name[0]


def update_user_last_seen(user_id: int) -> None:
    User.objects.filter(id=user_id).update(last_seen=timezone.now())


def get_current_date(as_string=False):
    """Return today's date. If as_string=True, return as 'DD.MM.YYYY'."""
    today = timezone.localdate()
    if as_string:
        return today.strftime('%d.%m.%Y')
    return today


def get_last_date_of_year(as_string=False):
    """Return December 31st of the current year. If as_string=True, return as 'DD.MM.YYYY'."""
    today = timezone.localdate()
    last_day = date(today.year, 12, 31)
    if as_string:
        return last_day.strftime('%d.%m.%Y')
    return last_day


def split_reg_number(full_number):
    match = re.match(r'^([^/]+)(/.*)$', full_number)
    if match:
        regSeria = match.group(1)  # '4'
        regNum = match.group(2)  # '/123'
        return regSeria, regNum
    else:
        return None, None


def number_to_uzbek_words(num):
    ones = ['', 'bir', 'ikki', 'uch', 'to‘rt', 'besh', 'olti', 'yetti', 'sakkiz', 'to‘qqiz']
    tens = ['', 'o‘n', 'yigirma', 'o‘ttiz', 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', 'to‘qson']

    if num == 0:
        return 'nol'

    words = ''

    if num >= 100:
        hundred = num // 100
        words += ones[hundred] + ' yuz'
        num = num % 100
        if num > 0:
            words += ' '

    if num >= 10:
        ten = num // 10
        words += tens[ten]
        num = num % 10
        if num > 0:
            words += ' '

    if num > 0:
        words += ones[num]

    return words.strip()


def calculate_years_and_months(start_date, end_date):
    # Convert to datetime if necessary
    if isinstance(start_date, date) and not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, datetime.min.time())
    elif isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if isinstance(end_date, date) and not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, datetime.min.time())
    elif isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    years = end_date.year - start_date.year
    months = end_date.month - start_date.month

    if months < 0:
        years -= 1
        months += 12

    if years < 0 or (years == 0 and months < 0):
        return "End date must be after start date"

    if years == 0:
        return f"{months} ({number_to_uzbek_words(months)}) oy"

    return f"{years} ({number_to_uzbek_words(years)}) yil" + \
        (f" {months} ({number_to_uzbek_words(months)}) oy" if months > 0 else "")


def get_app_label_and_model(
        obj: Union[Model, Type[Model], ContentType]) -> Tuple[str, str]:
    """
    Accepts:
      - a model instance,
      - a model class,
      - or a ContentType.

    Returns (app_label, model_name) suitable for
    ContentType.get_by_natural_key(app_label, model_name).
    """
    if isinstance(obj, ContentType):
        # ContentType already exposes the natural key parts
        return obj.app_label, obj.model  # note: ct.model is already lowercased

    meta = getattr(obj, "_meta", None)
    if meta is None:
        raise TypeError(
            "Expected a Django model instance/class or ContentType."
        )
    # meta.model_name is lowercased (matches ContentType.natural_key)
    return meta.app_label, meta.model_name


def get_content_type_id(obj: Union[Model, Type[Model], ContentType]) -> int:
    return ContentType.objects.get_for_model(obj).id


def _get_oracle_sql(query_name) -> str:
    """Fetch and cache the Oracle SQL once per task run."""
    try:
        return SQLQuery.objects.get(query_type=query_name).sql_query
    except Exception as e:
        raise


def format_uzbek_date(date: datetime.date) -> str:
    months = {
        1: "yanvar",
        2: "fevral",
        3: "mart",
        4: "aprel",
        5: "may",
        6: "iyun",
        7: "iyul",
        8: "avgust",
        9: "sentabr",
        10: "oktabr",
        11: "noyabr",
        12: "dekabr"
    }
    return f'“{date.day}” {months[date.month]} {date.year}-yil'


def check_if_workday(date: date) -> Tuple[bool, Dict[str, str]] | None:
    """
    Check if the given date is a workday according to IABSCalendar.
    Returns (True, {}) if it is a workday.
    Returns (False, {"info": ...}) if it is not a workday.
    Returns (False, {"error": ...}) if there is no calendar entry for the date.
    0 = non-working day, 1 = working day
    """
    try:
        calendar = IABSCalendar.objects.get(date=date)
        if calendar.work_day == 0:
            return False, {"info": f"Skipping {date}, not a work day"}
        return True, {}
    except IABSCalendar.DoesNotExist:
        return False, {"error": f"No calendar entry for date {date}"}
