import os
import re

import requests
from django.core.cache import cache
from django.utils.crypto import get_random_string

from apps.compose.models import Compose
from apps.user.models import User
from utils.exception import get_response_message, ValidationError2
from utils.tools import get_user_ip


class DigitalSignatureService:
    def __init__(self, model, document, document_id, request, pkcs7, class_name=None):
        self.request = request
        self.model = model
        self.document = document
        self.document_id = document_id
        self.pkcs7 = pkcs7
        self.type = class_name

    @property
    def headers(self):
        header = {
            'X-Real-IP': get_user_ip(self.request),
            'Host': os.getenv('E_IMZO_HOST')
        }
        return header

    def attache_timestamp(self):
        """
        This function is responsible for attaching timestamp to the pkcs7.
        """
        url = os.getenv('TIMESTAMP_URL')
        try:
            response = requests.post(url, data=self.pkcs7, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            message = get_response_message(self.request, 625)
            message['message'] = message['message'].format(e=e)
            raise ValidationError2(message)

    def verify_attached_pkcs7(self):
        """
        This function is responsible for verifying the pkcs7.
        """
        ts = self.attache_timestamp()
        pkcs7 = ts.get('pkcs7b64')
        url = os.getenv('VERIFY_ATTACHED')
        try:
            response = requests.post(url, headers=self.headers, data=pkcs7)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            message = get_response_message(self.request, 625)
            message['message'] = message['message'].format(e=e)
            raise ValidationError2(message)

    def certificate_info(self, tin, name, certificate, validate_date_start, validate_date_end, contract, created_at):
        data = f'STIR: {tin} / FIO: {name} (SERTIFIKAT: {certificate}, AMAL QILSIH DAVRI {validate_date_start} - ' \
               f'{validate_date_end}) / SHARTNOMA {contract}, {created_at}'
        return data

    def sign(self):
        data = self.verify_attached_pkcs7()

        if data.get('status') != 1:
            return _, data['message']

        signers = data['pkcs7Info']['signers'][0]
        signing_time = signers['signingTime']
        certificate_info = signers['certificate'][0]

        subject_name = certificate_info['subjectName']
        uid_span = re.search('UID', subject_name)
        inn = subject_name[uid_span.span()[1] + 1:uid_span.span()[1] + 10] if uid_span else '000000000'

        x1 = re.search("1.2.860.3.16.1.1", subject_name)  # yur - tin
        x2 = re.search("1.2.860.3.16.1.2", subject_name)  # fiz - id

        pinfl = subject_name[x1.span()[1] + 1:x1.span()[1] + 10] if x1 else (
            subject_name[x2.span()[1] + 1:x2.span()[1] + 15] if x2 else None
        )

        name = subject_name.split(',')[0][3:]
        current_user_pinfl = self.request.user.pinfl

        if pinfl == current_user_pinfl:
            user = self.get_user(pinfl)
        else:
            message = get_response_message(self.request, 624)
            raise ValidationError2(message)

        self.model.objects.create(
            author=user,
            pkcs7=self.pkcs7,
            pkcs7_info=data,
            signed=True,
            content=self.document,
            document_id=self.document_id,
            ip_addr=get_user_ip(self.request),
            type=self.type
        )

        # sign info data
        certificate_info = self.certificate_info(
            inn,
            name,
            certificate_info['serialNumber'],
            certificate_info['validFrom'],
            certificate_info['validTo'],
            self.document_id,
            signing_time
        )

        return 'ok', certificate_info

    def get_user(self, pinfl):
        try:
            user = User.objects.get(pinfl=pinfl)
        except User.MultipleObjectsReturned:
            message = get_response_message(self.request, 638)
            message['message'] = message['message'].format(object='e-imzo')
            raise ValidationError2(message)
        except User.DoesNotExist:
            message = get_response_message(self.request, 624)
            raise ValidationError2(message)

        if not user.is_active:
            message = get_response_message(self.request, 702)
            raise ValidationError2(message)

        if not user.is_registered:
            message = get_response_message(self.request, 703)
            raise ValidationError2(message)

        return user


class GenerateComposeRegisterNumber:
    def __init__(self, journal_index, journal_id):
        self.journal_index = journal_index
        self.journal_id = journal_id

    def generate(self):
        last_object = (Compose.objects.filter(journal_id=self.journal_id,
                                              register_number_int__isnull=False).
                       order_by('-register_number_int').first())
        new_register_number = last_object.register_number_int + 1
        return f"{self.journal_index}/{new_register_number}", new_register_number

    def generate_power_of_attorney_number(self):
        last_object = (Compose.objects.filter(journal_id=self.journal_id,
                                              register_number_int__isnull=False).
                       order_by('-register_number_int').first())
        # Calculate the new register number
        new_register_number = last_object.register_number_int + 1 if last_object else 1
        # Format the register number with leading zeros (e.g., "00001")
        formatted_register_number = str(new_register_number).zfill(5)  # 5 digits

        return f"ISH-{formatted_register_number}", new_register_number


class IABSRequestService:
    def __init__(self):
        self.url = os.getenv('IABS_REQUEST_SERVICE_URL')
        self.username = os.getenv('IABS_USERNAME')
        self.password = os.getenv('IABS_PASSWORD')
        self.cache_token_key = "iabs_token"

    def get_token(self):
        """
        This function is responsible for getting the token from the IABS service.
        """

        if cache.get(self.cache_token_key):
            return cache.get(self.cache_token_key)

        url = f"{self.url}/getToken"
        data = {
            'username': self.username,
            'password': self.password
        }
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            token = response.json().get('token')
            cache.set(self.cache_token_key, token, timeout=60 * 60 * 1)  # Cache the token for 1 hour
            return token
        except requests.exceptions.RequestException as e:
            message = {
                'status': 'fail',
                'message': f"IABS token olishda xato: {e}"
            }
            raise ValidationError2(message)

    def get_headers(self):
        token = self.get_token()
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'requestId': get_random_string(length=10),
            'Accept-Language': 'en',
        }

    def _send_request(self, url, data, endpoint=None):
        headers = self.get_headers()
        request_id = headers.get('requestId')
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            result['request_id'] = request_id
            return result
        except requests.exceptions.RequestException as e:
            msg = 'No response text available'
            if e.response is not None:
                try:
                    msg = e.response.json().get('msg', msg)
                except Exception:
                    msg = e.response.text or msg

            return {
                "code": -1,
                "status": "fail",
                "message": f"IABS xizmatiga murojaat qilishda xato: {e}",
                "details": msg,
                "endpoint": endpoint,
                "request_id": request_id
            }
        except Exception as e:
            return {
                "code": -1,
                "status": "fail",
                "message": f"IABS xizmatiga murojaat qilishda xato: {e}",
                "details": str(e),
                "endpoint": endpoint,
                "request_id": request_id
            }

    def create_order(self, data):
        url = f"{self.url}/1.0.0/create-order-doc"
        endpoint = '/1.0.0/create-order-doc'
        return self._send_request(url, data, endpoint=endpoint)

    def create_trip(self, data):
        url = f"{self.url}/1.0.0/create-trip"
        endpoint = '/1.0.0/create-trip'
        return self._send_request(url, data, endpoint=endpoint)

    def retry_action(self, data, endpoint):
        url = f"{self.url}{endpoint}"
        return self._send_request(url, data, endpoint=endpoint)
