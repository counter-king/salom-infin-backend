import six
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import _get_error_details, APIException

from apps.reference.models import ErrorMessage


class ValidationError2(APIException):
    """
    Custom exception class that is caught by Views Or Serializers
    and translated into readable format then sent it back to the UI
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Invalid input.')
    default_code = 'invalid'

    def __init__(self, detail, code=None, status_code=status.HTTP_400_BAD_REQUEST):
        self.status_code = status_code
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code

        # For validation failures, we may collect many errors together,
        # so the details should always be coerced to a list if not already.
        if not isinstance(detail, dict) and not isinstance(detail, list):
            detail = [detail]

        self.detail = _get_error_details(detail, code)

    def __str__(self):
        return six.text_type(self.detail)


class ErrorMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorMessage
        fields = ['message', 'status', 'status_code', 'code']


def get_response_message(request, code):
    if 'HTTP_ACCEPT_LANGUAGE' in request.META:
        language = request.META['HTTP_ACCEPT_LANGUAGE']
        translation.activate(language)

    error_message = ErrorMessage.objects.get(code=code)
    serializer = ErrorMessageSerializer(error_message)
    return serializer.data


class SocketClientError(Exception):
    """
    Custom exception class that is caught by the websocket receive()
    handler and translated into send back to the client.
    """

    def __init__(self, code, message):
        super().__init__(code)
        self.code = code
        if message:
            self.message = message


class SourceUnavailableError(RuntimeError):
    """Third party source not reachable or returning server errors."""
    pass
