import os
import re

import requests
from django.db.models import Q
from django.utils.crypto import get_random_string

from apps.user.models import User
from apps.user.services import send_otp_user
from utils.constants import CONSTANTS
from utils.exception import get_response_message, ValidationError2
from utils.tools import get_user_ip


class AuthWithEDS:
    """
    Class for authorization with Electronic Digital Signature
    Takes pkcs7 and validates it
    """

    def __init__(self, pkcs7, request):
        self.pkcs7 = pkcs7
        self.request = request

    @property
    def headers(self):
        header = {
            'X-Real-IP': get_user_ip(self.request),
            'Host': os.getenv('E_IMZO_HOST')
        }
        return header

    def attache_timestamp(self):
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

    def auth(self):
        data = self.verify_attached_pkcs7()

        if data.get('status') != 1:
            return _, data['message']

        signers = data['pkcs7Info']['signers'][0]
        certificate_info = signers['certificate'][0]

        subject_name = certificate_info['subjectName']
        uid_span = re.search('UID', subject_name)
        inn = subject_name[uid_span.span()[1] + 1:uid_span.span()[1] + 10] if uid_span else '000000000'

        x1 = re.search("1.2.860.3.16.1.1", subject_name)  # yur - tin
        x2 = re.search("1.2.860.3.16.1.2", subject_name)  # fiz - id

        pinfl = subject_name[x1.span()[1] + 1:x1.span()[1] + 10] if x1 else (
            subject_name[x2.span()[1] + 1:x2.span()[1] + 15] if x2 else None
        )

        user = self.get_user(pinfl)

        return user.tokens

    def get_user(self, pinfl):
        try:
            user = User.objects.get(pinfl=pinfl)
        except User.DoesNotExist:
            message = get_response_message(self.request, 624)
            raise ValidationError2(message)

        if not user.is_active:
            message = get_response_message(self.request, 702)
            raise ValidationError2(message)

        if not user.is_registered:
            message = get_response_message(self.request, 703)
            message['phone'] = user.phone
            self.send_verification_code(user)
            raise ValidationError2(message)

        return user

    def send_verification_code(self, user):
        """
        If user is not registered,
        send verification code to user's phone
        """
        user.otp = get_random_string(6, '0123456789')
        user.save()
        send_otp_user(user.phone, user.otp, CONSTANTS.OTP_TYPES.FOR_REGISTRATION)
