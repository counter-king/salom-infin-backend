from rest_framework import exceptions, status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTTokenUserAuthentication
from rest_framework_simplejwt.exceptions import TokenBackendError
from rest_framework_simplejwt.tokens import AccessToken
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed

from utils.exception import get_response_message, ValidationError2


class UserJSONWebTokenAuthentication(JWTTokenUserAuthentication):
    def authenticate_credentials(self, payload):
        """
        Returns an active user that matches the payload's user id and email.
        """
        User = get_user_model()

        try:
            access_token_obj = AccessToken(payload)
        except TokenBackendError as e:
            msg = get_response_message(payload, 704)
            raise ValidationError2(msg)

        username = access_token_obj.get('username') or None

        if not username:
            msg = _('Invalid payload.')
            raise exceptions.AuthenticationFailed(msg)
        try:
            user = User.objects.get_by_natural_key(username)
        except User.DoesNotExist:
            msg = _('Invalid signature.')
            raise exceptions.AuthenticationFailed(msg)

        if not user.is_user_active:
            msg = _('User account is disabled.')
            raise exceptions.AuthenticationFailed(msg)

        if not user.is_registered:
            msg = _('User not confirmed the registration')
            raise exceptions.AuthenticationFailed(msg, code='not_registered')

        iat = payload.get('orig_iat', 0)
        if not user or (user.password_update_time and user.password_update_time and iat < user.password_update_time):
            msg = _('Invalid token. Password has been changed.')
            raise exceptions.AuthenticationFailed(msg, code='401')
        return user


class JWTAuthenticationMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        try:
            user_jwt = UserJSONWebTokenAuthentication().authenticate(request)
            if user_jwt is not None:
                # store the first part from the tuple (user, obj)
                user = user_jwt[0]
                if not isinstance(user, AnonymousUser):
                    request.user = user
        except AuthenticationFailed as error:
            msg = get_response_message(request, 704)
            return JsonResponse(msg, status=status.HTTP_401_UNAUTHORIZED)
        return self.get_response(request)
