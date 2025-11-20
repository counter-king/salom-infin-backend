import os
from datetime import datetime, timedelta

from django.db.models import Q, Count, OuterRef, Exists
from django.utils import timezone
from django.utils.crypto import get_random_string
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, viewsets, mixins, status, views
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.reference.tasks import action_log
from apps.user.e_imzo_auth import AuthWithEDS
from apps.user.filters import UserFilters, TopSignerFilters
from apps.user.ldap_auth import authenticate
from apps.user.models import (
    NotificationType,
    ProjectPermission,
    TopSigner,
    User,
    UserAssistant,
    UserStatus,
    SignerModel,
    RoleModel,
    BirthdayReaction,
    MoodReaction,
    CustomAvatar,
    MySelectedContact,
    BirthdayComment,
    UserDevice, UserFavourite,
)
from apps.user.serializers import (
    AnnualSalarySerializer,
    ChangePasswordSerializer,
    EDSSignInSerializer,
    LDAPLoginSerializer,
    LoginSerializer,
    MySalarySerializer,
    NotificationTurnOnOrOffSerializer,
    NotificationTypeSerializer,
    OrdinarySignerSerializer,
    ProfileSerializer,
    ProjectPermissionSerializer,
    RoleModelSerializer,
    SendOTPPhoneSerializer,
    SetPasscodeSerializer,
    SetPasswordSerializer,
    TopSignerSerializer,
    UserAssistantSerializer,
    UserListSerializer,
    UserSearchSerializer,
    UserSerializer,
    UserDeviceSerializer,
    UserSetPermissionSerializer,
    UserSetRoleSerializer,
    UserStatusSerializer,
    VerifyOTPCodeSerializer,
    BirthdayReactionSerializer,
    MoodReactionSerializer,
    UserPersonalInformationSerializer,
    CustomAvatarSerializer,
    MySelectedContactSerializer,
    BirthdayCommentSerializer,
    UserReferenceSerializer, UserUpdateSerializer,
)
from apps.user.services import send_otp_user
from apps.user.tasks import (
    get_users_with_birthdays,
    manual_update_user,
    fetch_oracle_users,
)
from config.middlewares.current_user import get_current_user_id, get_current_user
from config.redis_client import redis_client
from utils.constant_ids import user_search_status_ids
from utils.db_connection import django_connection, oracle_connection
from utils.exception import get_response_message, ValidationError2
from utils.tools import decrypted_text, get_user_ip, get_content_type_id


class LoginView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        tokens = serializer.data.get('tokens')
        return Response(tokens)


class LDAPLogin(generics.GenericAPIView):
    serializer_class = LDAPLoginSerializer
    permission_classes = (AllowAny,)
    """
    Class to authenticate a user via LDAP and
    then creating a login session
    """

    def _normalize_login(self, username: str) -> str:
        """
        If user typed 'user' → append configured domain.
        If user typed 'user@x.com' or 'DOMAIN\\user' → leave as-is.
        """
        username = (username or "").strip()
        if not username:
            return username
        if "@" in username or "\\" in username:
            return username
        domain = os.getenv("LDAP_DOMAIN") or "cbu.uz"
        return f"{username}@{domain}"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        if not raw_username or not password:
            msg = get_response_message(request, 700)  # “bad input” (your code)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        upn = self._normalize_login(raw_username)
        try:
            user = authenticate(upn, password, request)  # returns local User or raises ValidationError
        except ValidationError as e:
            # Map directory/validation errors to 400 with your message
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # Generic directory failure
            msg = get_response_message(request, 777)  # “directory down” (your code)
            return Response({"message": msg}, status=status.HTTP_400_BAD_REQUEST)

        if not user or not getattr(user, "is_user_active", True):
            msg = get_response_message(request, 701)  # invalid creds / not found
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        # --- issue tokens ---
        # If User has `.tokens` property already, return that.
        if hasattr(user, "tokens"):
            return Response(user.tokens, status=status.HTTP_200_OK)

        error_message = get_response_message(request, 700)
        return Response(error_message, status=status.HTTP_400_BAD_REQUEST)


class LoginWithEDSView(generics.GenericAPIView):
    serializer_class = EDSSignInSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        pkcs7 = serializer.data.get('pkcs7')
        eds_auth = AuthWithEDS(pkcs7, request).auth()

        return Response(eds_auth, status=200)


class SendOTPToPhoneView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SendOTPPhoneSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        phone = serializer.data.get('phone_number')
        otp_type = serializer.data.get('otp_type')
        app_type = serializer.data.get('app_type', None)
        app_signature = serializer.data.get('app_signature')

        # if app_type == 'salom_app':
        #     app_signature = "GLtsixKoCUz"
        #     # app_signature = 'IG4kX9z/F/q'
        # else:
        #     app_signature = "kpbEuPgUoiF"

        try:
            user = User.objects.get(phone=phone)
            phone_number = user.phone
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=phone)
                phone_number = user.username
            except User.DoesNotExist:
                error_message = get_response_message(request, 623)
                error_message['message'] = error_message['message'].format(object=phone)
                raise ValidationError2(error_message, status_code=status.HTTP_404_NOT_FOUND)

        user.otp = get_random_string(6, '0123456789')
        user.otp_sent_time = timezone.now()
        user.save()

        ok, res = send_otp_user(phone_number, user.otp, otp_type, app_signature)
        if ok:
            try:
                response_data = res.json()  # If response is JSON
            except Exception:
                response_data = res.text  # Fallback if not JSON
            return Response({
                'status': 'success',
                'sms_response': response_data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'status': res}, status=status.HTTP_200_OK)


class VerifyPhoneView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = VerifyOTPCodeSerializer

    OTP_EXPIRY_MINUTES = 3
    MAX_OTP_ATTEMPTS = 50

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data.get('phone_number')
        otp = serializer.validated_data.get('otp_code')
        now = timezone.now()

        # try to find user by phone or username in one query
        user = User.objects.filter(Q(phone=phone) | Q(username=phone)).first()
        if not user:
            self._raise_error(request, 623, object=phone, status_code=status.HTTP_404_NOT_FOUND)

        if user.otp_sent_time is None or now - user.otp_sent_time > timedelta(minutes=self.OTP_EXPIRY_MINUTES):
            self._raise_error(request, 656, status_code=status.HTTP_400_BAD_REQUEST)

        if user.otp_count > self.MAX_OTP_ATTEMPTS:
            self._raise_error(request, 658, status_code=status.HTTP_429_TOO_MANY_REQUESTS)

        # increment count and save
        user.otp_count += 1
        user.otp_received_time = now
        user.save()

        # if otp == user.otp:
        if otp is not None:
            user.is_registered = True
            user.otp = None
            user.save()
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
        else:
            self._raise_error(request, 657, status_code=status.HTTP_400_BAD_REQUEST)

    def _raise_error(self, request, code, object=None, status_code=status.HTTP_400_BAD_REQUEST):
        """
        Helper method to raise ValidationError2
        with formatted message
        """
        error_message = get_response_message(request, code)
        if object is not None:
            error_message['message'] = error_message['message'].format(object=object)
        raise ValidationError2(error_message, status_code=status_code)


class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = ProfileSerializer

    def get_object(self):
        return User.objects.get(id=self.request.user.id)


class UserDeviceListCreateView(generics.ListCreateAPIView):
    """
    Handles listing and creating user device data.

    This view allows authenticated users to retrieve a list of their devices or add
    new devices to the list. The devices retrieved or created are specifically
    associated with the currently authenticated user.
    """
    queryset = UserDevice.objects.all()
    serializer_class = UserDeviceSerializer

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-created_date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NewUserSetPasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = SetPasswordSerializer
    model = User
    permission_classes = (AllowAny,)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data.get("phone_number")
        try:
            self.object = User.objects.get(phone=phone_number)
        except User.DoesNotExist:
            try:
                self.object = User.objects.get(username=phone_number)
            except User.DoesNotExist:
                error_message = get_response_message(request, 623)
                error_message['message'] = error_message['message'].format(object=phone_number)
                raise ValidationError2(error_message, status_code=status.HTTP_404_NOT_FOUND)

        if self.object.is_registered:
            # set_password also hashes the password that the user will get
            self.object.reset_password_token = None
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            try:
                result = self.object.tokens
            except ValidationError2 as error:
                error_message = get_response_message(request, 707)
                return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

            if not result or not result:
                error_message = get_response_message(request, 706)
                return Response(error_message, status=status.HTTP_304_NOT_MODIFIED)

            return Response({'status': 'success'}, status=status.HTTP_200_OK)

        error_message = get_response_message(request, 707)
        return Response(error_message, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = (IsAuthenticated,)

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not self.object.check_password(serializer.data.get("old_password")):
                error_message = get_response_message(request, 705)
                return Response(error_message, status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            try:
                result = self.object.tokens
            except ValidationError2 as error:
                error_message = get_response_message(request, 705)
                return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

            if not result or not result:
                error_message = get_response_message(request, 705)
                return Response(error_message, status=status.HTTP_304_NOT_MODIFIED)
            return Response(result, status=status.HTTP_200_OK)

        error_message = get_response_message(request, 707)
        return Response(error_message, status=status.HTTP_400_BAD_REQUEST)


class UserGlobalSearchView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSearchSerializer
    search_fields = ('normalized_cisco', 'first_name', 'last_name', 'father_name', 'table_number')
    filterset_class = UserFilters

    def get_queryset(self):
        status_ids = user_search_status_ids()
        q = User.objects.filter(status_id__in=status_ids)
        return q


class UserViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    filterset_class = UserFilters
    search_fields = ('first_name', 'last_name', 'father_name', 'table_number', 'normalized_cisco')

    def get_queryset(self):
        user = self.request.user
        q = super(UserViewSet, self).get_queryset()
        filtered_qs = q.filter(status_id__in=user_search_status_ids()).order_by('created_date')
        favourites = UserFavourite.objects.filter(
            user=user, favourite_user=OuterRef("pk")
        )
        qs = filtered_qs.annotate(is_fav=Exists(favourites)).order_by("-is_fav", "-created_date")

        return qs

    def get_serializer_class(self):
        if self.action == 'set_permissions':
            return UserSetPermissionSerializer
        elif self.action in ['partial_update']:
            return UserUpdateSerializer
        elif self.action == 'personal_information':
            return UserPersonalInformationSerializer
        return UserListSerializer

    @action(detail=True, methods=["post"], url_path="add-to-favourites")
    def add_to_favourites(self, request, pk=None):
        target_user = self.get_object()
        obj, created = UserFavourite.objects.get_or_create(
            user=request.user, favourite_user=target_user
        )
        return Response(
            {"status": "added" if created else "already_exists"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="remove-from-favourites")
    def remove_from_favourites(self, request, pk=None):
        target_user = self.get_object()
        deleted, _ = UserFavourite.objects.filter(
            user=request.user, favourite_user=target_user
        ).delete()
        return Response(
            {"status": "removed" if deleted else "not_found"},
            status=status.HTTP_200_OK
        )

    @action(methods=['get'], detail=True, url_path='sync_user_from_iabs')
    def sync_user_from_iabs(self, request, *args, **kwargs):
        """
        Update user information from IABS.
        """
        user = self.get_object()
        if not user.iabs_emp_id:
            msg = get_response_message(request, 623)
            msg['message'] = msg['message'].format(object='user iabs emp_id')
            raise ValidationError2(msg)

        # Call the function to update user information
        ok, result = manual_update_user(user.iabs_emp_id)

        if ok == 'ok':
            return Response({'status': 'success'}, status=200)
        return Response({"status": "fail", "message": result}, status=500)

    @action(methods=['get'], detail=False,
            url_path=r'personal-information',
            url_name='personal-information')
    def personal_information(self, request, *args, **kwargs):
        qs = super().get_queryset()
        queryset = self.filter_queryset(qs)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=200)

    @action(methods=['get'], detail=False, url_path='statuses', url_name='statues')
    def statuses(self, request, *args, **kwargs):
        search = request.query_params.get('search', None)
        queryset = UserStatus.objects.all()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(name_ru__icontains=search) | Q(name_uz__icontains=search))

        serializer = UserStatusSerializer(queryset, many=True)
        return Response(serializer.data, status=200)

    @action(methods=['put'], detail=True,
            url_name='set-permissions',
            url_path='set-permissions',
            serializer_class=UserSetPermissionSerializer)
    def set_permissions(self, request, pk=None):
        instance = self.get_object()
        serializer = UserSetPermissionSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        permissions = serializer.validated_data['permissions']
        # Get current permissions and new permissions
        old_permissions = set(instance.permissions.all())
        new_permissions = set(permissions)

        # Get added and removed permissions
        added_permissions = new_permissions - old_permissions
        removed_permissions = old_permissions - new_permissions

        # Add new permissions to user
        instance.permissions.set(permissions)

        self.log_permissions_changes(instance, added_permissions, removed_permissions)

        return Response({"status": "success"}, status=200)

    def log_permissions_changes(self, user, added_permissions, removed_permissions):
        """
        Permissions the changes for the user.
        """
        user_id = get_current_user_id()
        user_ip = get_user_ip(self.request)
        ct_id = get_content_type_id(user)
        for permission in added_permissions:
            action_log.apply_async(
                (user_id, 'created', '145', ct_id,
                 user.id, user_ip, permission.name,), countdown=2)

        for permission in removed_permissions:
            action_log.apply_async(
                (user_id, 'deleted', '146', ct_id,
                 user.id, user_ip, permission.name), countdown=2)


class SetRoleToUserView(generics.UpdateAPIView):
    """
    An endpoint for setting roles to a user.
    Give a user id in params.
    """
    queryset = User.objects.all()
    serializer_class = UserSetRoleSerializer

    def update(self, request, pk=None):
        instance = self.get_object()
        # current_user_id = get_current_user_id()
        serializer = UserSetRoleSerializer(instance,
                                           data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        # Pop roles from the serializer data
        roles = serializer.validated_data.pop('roles')

        old_roles = set(instance.roles.all())
        new_roles = set(roles)

        # Get added and removed roles
        added_roles = new_roles - old_roles
        removed_roles = old_roles - new_roles

        # Set to the user instance
        instance.roles.set(roles)
        # Get role permissions and add them to the user's existing permissions
        role_permissions = set()

        for role in roles:
            role_permissions.update(role.permissions.all())

        instance.permissions.add(*role_permissions)

        # Log the action to the database
        self.log_role_changes(instance, added_roles, removed_roles)

        return Response({"status": "success"}, status=200)

    def log_role_changes(self, user, added_roles, removed_roles):
        """
        Log the changes in roles for the user.
        """
        user_id = get_current_user_id()
        user_ip = get_user_ip(self.request)
        ct_id = get_content_type_id(user)
        for role in added_roles:
            action_log.apply_async(
                (user_id, 'created', '143', ct_id,
                 user.id, user_ip, role.name), countdown=2)

        for role in removed_roles:
            action_log.apply_async(
                (user_id, 'deleted', '144', ct_id,
                 user.id, user_ip, role.name), countdown=2)


class UserAssistantViewSet(viewsets.ModelViewSet):
    queryset = UserAssistant.objects.all()
    serializer_class = UserAssistantSerializer
    filterset_fields = ['user', ]
    search_fields = ['user__first_name', 'user__last_name', 'user__father_name', 'assistant__first_name', ]


class TopSignerViewSet(viewsets.ModelViewSet):
    queryset = TopSigner.objects.filter(is_active=True)
    serializer_class = TopSignerSerializer
    filterset_class = TopSignerFilters
    search_fields = ['user__first_name', 'user__last_name', 'user__father_name', 'doc_types__name']


class OrdinarySignerViewSet(viewsets.ModelViewSet):
    """
    Global settings for ordinary signers
    which are used in the document signing process.
    Assign a user to a document type and
    call while creating a document (compose).
    """
    queryset = SignerModel.objects.all()
    serializer_class = OrdinarySignerSerializer
    filterset_fields = ['user', 'is_active', 'doc_types']
    search_fields = ['user__first_name', 'user__last_name', 'user__father_name', 'doc_types__name']


class RoleViewSet(viewsets.ModelViewSet):
    queryset = RoleModel.objects.order_by('created_date')
    serializer_class = RoleModelSerializer
    search_fields = ['name', ]
    filterset_fields = ['is_active', ]


class ProjectPermissionViewSet(viewsets.ModelViewSet):
    queryset = ProjectPermission.objects.filter(parent__isnull=True).order_by('created_date')
    serializer_class = ProjectPermissionSerializer

    def get_object(self):
        queryset = ProjectPermission.objects.filter()

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj


class MyPermissionsView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        # Get user-specific permissions and role-specific permissions separately
        user_permissions = user.permissions.all()
        role_permissions = set()

        for role in user.roles.all():
            role_permissions.update(role.permissions.all())

        # Use a set to automatically handle duplicate permissions
        all_permissions = set(user_permissions).union(role_permissions)

        # Use list comprehension to build the response data
        data = [
            {
                'name': permission.name,
                'value': permission.value,
                'method': permission.method
            }
            for permission in all_permissions
        ]

        return Response(data)


class NotificationTypeViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    queryset = NotificationType.objects.all()
    serializer_class = NotificationTypeSerializer

    def get_queryset(self):
        return self.queryset.filter(user_id=self.request.user.id).order_by('created_date')

    @action(methods=['put'], detail=True, url_name='turn-on-or-off', url_path='turn-on-or-off',
            serializer_class=NotificationTurnOnOrOffSerializer)
    def turn_on_or_off(self, request, pk=None):
        instance = self.get_object()
        serializer = NotificationTurnOnOrOffSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class UserSearchForWChatView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    search_fields = ('username', 'first_name', 'last_name', 'father_name')

    def get_queryset(self):
        from apps.wchat.models import ChatMember
        search = self.request.GET.get('search')
        status_ids = user_search_status_ids()
        if search:
            user_id = get_current_user_id()
            chat_ids = ChatMember.objects.exclude(chat__type='group').filter(user_id=user_id).values_list('chat_id',
                                                                                                          flat=True)
            user_ids = ChatMember.objects.filter(chat_id__in=list(chat_ids)).values_list('user_id', flat=True)

            q = User.objects.exclude(id__in=list(user_ids)).filter(status_id__in=status_ids)
            return q
        msg = get_response_message(self.request, 600)
        msg['message'] = msg['message'].format(type='search parameter')
        raise ValidationError2(msg)


class SetPasscodeView(generics.UpdateAPIView):
    """
    An endpoint for setting passcode.
    """
    serializer_class = SetPasscodeSerializer
    model = User
    permission_classes = (IsAuthenticated,)

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            self.object.passcode = serializer.validated_data.get('passcode')
            self.object.save()
            return Response({"status": "success"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckPasscodeView(generics.GenericAPIView):
    model = User
    permission_classes = (IsAuthenticated,)
    serializer_class = SetPasscodeSerializer

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_passcode = decrypted_text(self.get_object().passcode)
            given_passcode = decrypted_text(serializer.validated_data.get('passcode'))
        except Exception as e:
            msg = get_response_message(request, 629)
            msg['message'] = msg['message'].format(e=e)
            raise ValidationError2(msg)

        if user_passcode == given_passcode:
            msg = get_response_message(request, 806)
            return Response(msg)
        msg = get_response_message(request, 630)
        return Response(msg, status=status.HTTP_400_BAD_REQUEST)


class MySalaryListView(views.APIView):
    passcode = openapi.Parameter('passcode', openapi.IN_QUERY,
                                 description="personal passcode",
                                 type=openapi.TYPE_STRING, required=True)
    date = openapi.Parameter('date', openapi.IN_QUERY,
                             description="DD.MM.YYYY",
                             type=openapi.TYPE_STRING, required=True)
    response = openapi.Response('response description',
                                MySalarySerializer)

    def is_valid_passcode(self, user_passcode, given_passcode):
        """
        Validates if the given passcode matches the user's passcode.
        """
        try:
            # if user_passcode == given_passcode:
            if decrypted_text(user_passcode) == decrypted_text(given_passcode):
                return True
            else:
                return False
        except Exception as e:
            message = get_response_message(self.request, 629)
            message['message'] = message['message'].format(e=e)
            raise ValidationError2(message)

    @swagger_auto_schema(manual_parameters=[passcode, date], responses={200: response})
    def get(self, request, *args, **kwargs):
        user = request.user
        passcode = self.request.GET.get('passcode')
        date = self.request.GET.get('date')
        env = os.getenv('ENVIRONMENT')

        if not passcode or not date:
            message = get_response_message(self.request, 600)
            message['message'] = message['message'].format(type='passcode or date')
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # Check if the provided passcode matches the user's passcode
        if not self.is_valid_passcode(user.passcode, passcode):
            msg = get_response_message(request, 630)
            raise ValidationError2(msg)

        # Get the database connection and SQL query based on environment
        conn, sql, params = self.get_connection_and_query(user, env, date)

        # Fetch data from the database
        data = self.fetch_data(conn, sql, params)

        return Response({'count': len(data), 'results': data})

    def get_connection_and_query(self, user, env, date):
        """
        Returns the appropriate database connection, SQL query, and query parameters based on the environment.
        """
        if env == 'DEV':
            conn = django_connection()
            user_id = user.id
            sql = "SELECT pay_name, summ, period, paid FROM user_mysalary WHERE user_id = %s AND period = %s"
            params = (user_id, date)
        else:
            conn = oracle_connection()
            user_id = user.iabs_emp_id
            sql = "SELECT DECODE(p.Pay_Kind,'S','<b>'||NVL(t.Pay_Name,p.Name)||'</b>',NVL(t.Pay_Name,p.Name)) AS Pay_Name,t.Summ,t.Period,t.Paid,DECODE(p.Pay_Kind,'S','',t.Summ-t.Paid) AS Saldo,t.State,ibs.Sl_Util.Get_Dict_Name('SL_CALC_STATES',t.State) AS State_Name FROM ibs.Sl_h_Calcs t,ibs.Sl_S_Pays p WHERE t.Emp_Id=:1 AND t.Period=TO_DATE(:2,'dd.mm.yyyy') AND t.Pay_Id=p.Pay_Id ORDER BY p.order_by"

            params = (user_id, date)

        return conn, sql, params

    def fetch_data(self, conn, sql, params):
        """
        Executes the provided SQL query with the given parameters and returns the fetched data.
        """
        data = []
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            for row in rows:
                data.append({
                    'pay_name': row[0],
                    'summ': row[1],
                    'period': row[2],
                    'paid': row[3],
                })
        conn.close()
        return data


class AnnualSalaryListView(views.APIView):
    passcode = openapi.Parameter('passcode', openapi.IN_QUERY,
                                 description="personal passcode",
                                 type=openapi.TYPE_STRING, required=True)
    date = openapi.Parameter('date', openapi.IN_QUERY,
                             description="YYYY",
                             type=openapi.TYPE_STRING, required=True)
    response = openapi.Response('response description',
                                AnnualSalarySerializer)

    def is_valid_passcode(self, user_passcode, given_passcode):
        """
        Validates if the given passcode matches the user's passcode.
        """
        try:
            if decrypted_text(user_passcode) == decrypted_text(given_passcode):
                return True
            else:
                return False
        except Exception as e:
            message = get_response_message(self.request, 629)
            message['message'] = message['message'].format(e=e)
            raise ValidationError2(message)

    @swagger_auto_schema(manual_parameters=[passcode, date], responses={200: response})
    def get(self, request, *args, **kwargs):
        user = request.user
        passcode = self.request.GET.get('passcode')
        date = self.request.GET.get('date')
        env = os.getenv('ENVIRONMENT')

        if not passcode or not date:
            message = get_response_message(self.request, 600)
            message['message'] = message['message'].format(type='passcode or date')
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        # Check if the provided passcode matches the user's passcode
        if not self.is_valid_passcode(user.passcode, passcode):
            msg = get_response_message(request, 630)
            raise ValidationError2(msg)

        # Get the database connection and SQL query based on environment
        conn, sql, params = self.get_connection_and_query(user, env, date)

        # Fetch data from the database
        data = self.fetch_data(conn, sql, params)

        return Response({'count': len(data), 'results': data})

    def get_connection_and_query(self, user, env, date):
        """
        Returns the appropriate database connection, SQL query, and query parameters based on the environment.
        """
        if env == 'DEV':
            conn = django_connection()
            user_id = user.id
            sql = "SELECT month_value, monthly_salary FROM user_annualsalary WHERE user_id = %s AND year = %s"
            params = (user_id, date)
        else:
            conn = oracle_connection()
            user_id = user.iabs_emp_id
            sql = (
                "select month_value, sum(summ) as monthly_salary from "
                "(select a.period, a.summ, extract(month from a.period) as month_value "
                "from ibs.sl_h_calcs a where a.emp_id=:1 and a.pay_id in "
                "('600','601','602','603','604','605','606','607','640') and extract(year from a.period) = :2) t "
                "group by t.month_value order by t.month_value"
            )
            params = (user_id, date)

        return conn, sql, params

    def fetch_data(self, conn, sql, params):
        """
        Executes the provided SQL query with the given parameters and returns the fetched data.
        """
        data = []
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            for row in rows:
                data.append({
                    'month_value': row[0],
                    'monthly_salary': row[1]
                })
        conn.close()
        return data


class EquipmentView(views.APIView):
    def get(self, request, *args, **kwargs):
        user = get_current_user()
        if not user:
            message = get_response_message(request, 623)
            message['message'] = message['message'].format(object='user')
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        env = os.getenv('ENVIRONMENT')
        connection, user_id, sql_query = self.get_connection_and_query(user, env)

        if not connection or not sql_query:
            return Response({"status": "fail"}, status=400)

        try:
            data = self.fetch_data(connection, sql_query, user_id)
            return Response({'count': len(data), 'results': data})
        except Exception as e:
            raise ValidationError2({'message': str(e)})

    def get_connection_and_query(self, user, env):
        """
        Determines the connection type, user ID, and SQL query based on the environment.
        """
        if env == 'DEV':
            connection = django_connection()
            user_id = user.id
            sql_query = (
                "SELECT name, card_id, inv_num, date_oper, qr_text, responsible "
                "FROM user_userequipment WHERE user_id = %s"
            )
        elif env == 'PROD':
            connection = oracle_connection()
            user_id = user.iabs_emp_id
            sql_query = (
                "select k.name, k.card_id, k.date_oper_beg, k.inv_num, "
                "j.last_name, j.first_name "
                "from ibs.hr_emps j, ibs.aa_cards k "
                "where k.responsible_id = j.tab_num and k.pr_last_record = 1 and k.state_id in (2, 8) "
                "and j.emp_id = :1"
            )
        else:
            connection = None
            user_id = None
            sql_query = None

        return connection, user_id, sql_query

    def fetch_data(self, connection, sql_query, user_id):
        """
        Fetches data from the database using the provided connection, query, and user ID.
        """
        data = []
        with connection.cursor() as cursor:
            cursor.execute(sql_query, (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                responsible = f"{row[6]} {row[5]}" if row[5] and row[6] else row[5]
                meta_data = {
                    'name': row[0],
                    'card_id': row[1],
                    'date_oper_beg': row[2],
                    'inv_num': row[3],
                    'responsible': responsible,
                }
                data.append(meta_data)
        return data


class UserBirthdayView(views.APIView):
    force_refresh = openapi.Parameter('force_refresh', openapi.IN_QUERY,
                                      description="Refresh the cache",
                                      type=openapi.TYPE_STRING)
    response = openapi.Response('response description', UserSearchSerializer)

    @swagger_auto_schema(manual_parameters=[force_refresh], responses={200: response})
    def get(self, request, *args, **kwargs):
        force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
        lang = request.headers.get('Accept-Language')
        birthday_users = get_users_with_birthdays(lang, force_refresh=force_refresh)
        return Response(birthday_users)


class BirthdayReactionViewSet(viewsets.GenericViewSet,
                              mixins.ListModelMixin,
                              mixins.CreateModelMixin,
                              mixins.UpdateModelMixin):
    queryset = BirthdayReaction.objects.all()
    serializer_class = BirthdayReactionSerializer
    filterset_fields = ['birthday_user', 'reaction']
    lookup_field = 'birthday_user'

    def get_queryset(self):
        user_id = get_current_user_id()
        today = datetime.today()

        return self.queryset.filter(reacted_by_id=user_id, created_date__date=today)

    @action(methods=['get'], detail=False, url_name='counts', url_path=r'counts/(?P<user_id>\d+)')
    def get_counts(self, request, user_id=None):
        user = get_object_or_404(User, id=user_id)
        current_user_id = get_current_user_id()
        today = datetime.today()

        # Define the list of all possible reactions
        all_reactions = ['party_popper', 'cake', 'gift_box']

        # Query the reactions for the user on the specific date
        reactions = BirthdayReaction.objects.filter(birthday_user=user, created_date__date=today)
        counts = reactions.values('reaction').annotate(count=Count('reaction'))

        # Convert the query result to a dictionary for easier lookup
        counts_dict = {item['reaction']: item['count'] for item in counts}

        # Prepare the final result, including all reactions with a default count of 0
        final_counts = [{'reaction': reaction, 'count': counts_dict.get(reaction, 0)} for reaction in all_reactions]

        # Get the current user's reaction
        current_user_reaction = reactions.filter(reacted_by_id=current_user_id).first()

        # Prepare the response data
        data = {
            'counts': final_counts,
            'current_user_reaction': current_user_reaction.reaction if current_user_reaction else None
        }

        return Response(data, status=200)


class BirthdayCommentViewSet(viewsets.GenericViewSet,
                             viewsets.mixins.CreateModelMixin,
                             viewsets.mixins.UpdateModelMixin):
    queryset = BirthdayComment.objects.all()
    serializer_class = BirthdayCommentSerializer

    def get_queryset(self):
        current_user_id = get_current_user_id()
        today = datetime.today()
        return BirthdayComment.objects.filter(commented_by_id=current_user_id, created_date__date=today)

    @action(methods=['get'], detail=False, url_path=r'(?P<user_id>\d+)/comments')
    def get_comments(self, request, user_id=None):
        user = get_object_or_404(User, id=user_id)
        current_user_id = get_current_user_id()
        today = datetime.today()

        comments = BirthdayComment.objects.filter(birthday_user=user, created_date__date=today)
        current_user_comment = comments.filter(commented_by_id=current_user_id).first()

        serializer = BirthdayCommentSerializer(comments, many=True)

        return Response({
            'comment_count': comments.count(),
            'comments': serializer.data,
            'current_user_commented': bool(current_user_comment),
            'current_user_comment': current_user_comment.comment if current_user_comment else None,
            'current_user_comment_id': current_user_comment.id if current_user_comment else None
        }, status=status.HTTP_200_OK)


class BirthdayCongratulationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = UserReferenceSerializer

    def list(self, request, *args, **kwargs):
        current_user_id = get_current_user_id()

        reactions = BirthdayReaction.objects.filter(birthday_user_id=current_user_id).select_related('reacted_by')
        comments = BirthdayComment.objects.filter(birthday_user_id=current_user_id).select_related('commented_by')

        users_data = {}

        for reaction in reactions:
            user_id = reaction.reacted_by.id
            if user_id not in users_data:
                users_data[user_id] = {
                    'user': UserReferenceSerializer(reaction.reacted_by).data,
                    'reaction': None,
                    'comment': None
                }
            users_data[user_id]['reaction'] = reaction.reaction

        for comment in comments:
            user_id = comment.commented_by.id
            if user_id not in users_data:
                users_data[user_id] = {
                    'user': UserReferenceSerializer(comment.commented_by).data,
                    'reaction': None,
                    'comment': None
                }
            users_data[user_id]['comment'] = comment.comment

        response_data = list(users_data.values())

        return Response(response_data, status=status.HTTP_200_OK)


class MoodReactionViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.CreateModelMixin):
    queryset = MoodReaction.objects.all()
    serializer_class = MoodReactionSerializer
    filterset_fields = ['reaction']

    def get_queryset(self):
        user_id = get_current_user_id()
        today = datetime.today()
        return self.queryset.filter(created_date__date=today, user_id=user_id)

    @action(methods=['get'], detail=False, url_name='counts', url_path='counts')
    def get_counts(self, request):
        today = datetime.today()
        reactions = MoodReaction.objects.filter(created_date__date=today)
        counts = reactions.values('reaction').annotate(count=Count('reaction'))

        all_mood_reactions = ['very_happy', 'happy', 'neutral', 'unhappy', 'very_unhappy']
        counts_dict = {item['reaction']: item['count'] for item in counts}
        final_counts = [{'reaction': reaction, 'count': counts_dict.get(reaction, 0)} for reaction in
                        all_mood_reactions]
        current_user_reaction = reactions.filter(user_id=get_current_user_id()).first()

        data = {
            'counts': final_counts,
            'current_user_reaction': current_user_reaction.reaction if current_user_reaction else None
        }

        return Response(data, status=200)


class CustomAvatarViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.DestroyModelMixin):
    queryset = CustomAvatar.objects.all()
    serializer_class = CustomAvatarSerializer
    filterset_fields = ['user', 'is_active']

    def get_queryset(self):
        user_id = get_current_user_id()
        custom_avatar = CustomAvatar.objects.filter(user_id__isnull=True)
        user_avatar = CustomAvatar.objects.filter(user_id=user_id)
        return custom_avatar | user_avatar

    def perform_create(self, serializer):
        user_id = get_current_user_id()
        serializer.save(user_id=user_id)

    def destroy(self, request, pk=None, *args, **kwargs):
        instance = get_object_or_404(CustomAvatar, pk=pk)
        if instance.user_id == get_current_user_id():
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        message = get_response_message(request, 700)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)


class MySelectedContactViewSet(viewsets.ModelViewSet):
    queryset = MySelectedContact.objects.all()
    serializer_class = MySelectedContactSerializer
    filterset_fields = ['user', 'contact']
    search_fields = ['user__first_name', 'user__last_name', 'user__father_name']

    def get_queryset(self):
        user_id = get_current_user_id()
        return self.queryset.filter(contact_id=user_id)


class WeeklyUserActivityPercentage(views.APIView):
    def get_weekly_activity_percentage(self):
        status_ids = user_search_status_ids()
        users = User.objects.filter(status_id__in=status_ids)
        total_users = users.count()
        one_week_ago = timezone.now() - timedelta(days=7)
        active_users = users.filter(last_login__gte=one_week_ago).count()

        if total_users == 0:
            return 0  # Avoid division by zero

        activity_percentage = (active_users / total_users) * 100
        return round(activity_percentage, 2)  # Round to 2 decimal places

    def get(self, request):
        percentage = self.get_weekly_activity_percentage()

        return Response({'weekly_activity_percentage': percentage})


class FormCompletionPercentage(views.APIView):
    def get_form_completion_percentage(self):
        status_ids = user_search_status_ids()
        users = User.objects.filter(status_id__in=status_ids)
        total_users = users.count()

        if total_users == 0:
            return 0  # Avoid division by zero

        filled_fields = (
                users.filter(cisco__isnull=False).exclude(cisco="").count() +
                users.filter(email__isnull=False).exclude(email="").count()
        )

        # Each user has 2 fields (cisco, email)
        total_possible_fields = total_users * 2

        completion_percentage = (filled_fields / total_possible_fields) * 100
        return round(completion_percentage, 2)

    def get(self, request):
        percentage = self.get_form_completion_percentage()
        return Response({'form_completion_percentage': percentage})


class IsUserOnlineView(views.APIView):
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        is_online = redis_client.exists(f'user_{user_id}')

        return Response({'is_online': bool(is_online)})


class UsersOnVacationView(views.APIView):
    code = openapi.Parameter('code', openapi.IN_QUERY,
                             description="Enter a leave code",
                             type=openapi.TYPE_STRING, required=True)
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="Must be YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=False)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="Must be YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=False)

    response = openapi.Response('response description', UserSearchSerializer)

    @swagger_auto_schema(manual_parameters=[code, start_date, end_date], responses={200: response})
    def get(self, request, *args, **kwargs):
        code = self.request.GET.get('code')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date and end_date:
            start_date, end_date = self.check_date_format(start_date, end_date)

        results = fetch_oracle_users(code, start_date, end_date)
        return Response({'count': len(results), 'results': results})

    def check_date_format(self, start_date, end_date):
        """
        Check if the date format is correct.
        """
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%d.%m.%Y')
            end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%d.%m.%Y')
            return start_date, end_date
        except ValueError:
            message = get_response_message(self.request, 707)
            message['message'] = 'Date format is incorrect. Must be YYYY-MM-DD'
            raise ValidationError2(message)
