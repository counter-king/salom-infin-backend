# middleware/log_request_body.py
import json
import logging

logger = logging.getLogger('request_logger')

sensitive_fields = [
    'password',
    'confirm_password',
    'old_password',
    'new_password',
    'username',
    'email',
    'phone_number',
    'card_number',
    'ssn',
    'token',
]


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        method = request.method

        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                body = request.body.decode("utf-8")
                data = json.loads(body) if body else {}

                for field in sensitive_fields:
                    if field in data:
                        data[field] = "*****"

            except Exception:
                data = "Unparsable body"

            logger.info(f"{method} {request.path} - Body: {data}")

        response = self.get_response(request)
        return response
