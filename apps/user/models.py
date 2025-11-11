import random
from datetime import datetime

from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from base_model.models import BaseModel
from config.redis_client import redis_client
from utils.constants import COLORS, CONSTANTS


# Create your models here.

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None):
        """
        Creates and saves a User with the given username, date of
        birth and password.
        """
        if not username:
            raise ValueError(_('Users must have an username address'))

        user = self.model(
            username=username.strip(),
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password):
        """
        Creates and saves a superuser with the given username, date of
        birth and password.
        """
        user = self.create_user(
            username,
            password=password
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.is_registered = True
        user.save(using=self._db)
        return user


class UserStatus(BaseModel):
    name = models.CharField(max_length=255, null=True)
    code = models.CharField(max_length=10, null=True)
    code_type = models.CharField(max_length=10, null=True)
    sort_ord = models.IntegerField(default=0)
    included_in_search = models.BooleanField(default=False)
    strict_condition = models.BooleanField(default=False)
    is_reasonable = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'User Statuses'

    def dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
        }


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    username = models.CharField(blank=True, null=True, max_length=250, unique=True)
    ldap_login = models.CharField(blank=True, null=True, max_length=50)
    email = models.EmailField(blank=True, null=True)
    cisco = models.CharField(blank=True, null=True, max_length=10)
    normalized_cisco = models.CharField(blank=True, null=True, max_length=10)
    avatar = models.ForeignKey('document.File', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True)
    top_level_department = models.ForeignKey(
        'company.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='parent_department')
    department = models.ForeignKey(
        'company.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees')
    position = models.ForeignKey(
        'company.Position',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    department_ids = ArrayField(models.IntegerField(), null=True, blank=True)
    status = models.ForeignKey(UserStatus, on_delete=models.SET_NULL, null=True, blank=True)
    is_user_active = models.BooleanField(default=True)
    is_registered = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    father_name = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=250, null=True, blank=True)
    phone_2 = models.CharField(max_length=250, null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    color = models.CharField(max_length=10, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    pinfl = models.CharField(max_length=20, null=True, blank=True)
    tin = models.CharField(max_length=9, null=True, blank=True)
    begin_work_date = models.DateField(null=True, blank=True,
                                       help_text='Date when the employee begins work')
    end_date = models.DateTimeField(null=True, blank=True,
                                    help_text='Date when the employee leaves the company')
    table_number = models.CharField(max_length=50, null=True, blank=True)
    unique_number = models.CharField(max_length=50, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_sent_time = models.DateTimeField(null=True, blank=True)
    otp_received_time = models.DateTimeField(null=True, blank=True)
    otp_count = models.IntegerField(default=0)
    permissions = models.ManyToManyField('user.ProjectPermission', blank=True)
    roles = models.ManyToManyField('user.RoleModel', blank=True)
    iabs_emp_id = models.IntegerField(null=True, blank=True)
    iabs_staffing_id = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, null=True, blank=True)
    passcode = models.CharField(max_length=255, null=True, blank=True)
    passport_seria = models.CharField(max_length=5, null=True, blank=True)
    passport_number = models.CharField(max_length=10, null=True, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    passport_expiry_date = models.DateField(null=True, blank=True)
    passport_issued_by = models.CharField(max_length=255, null=True, blank=True)
    room_number = models.CharField(max_length=50, null=True, blank=True)
    work_address = models.CharField(max_length=255, null=True, blank=True)
    floor = models.CharField(max_length=50, null=True, blank=True)
    show_mobile_number = models.BooleanField(default=False)
    show_birth_date = models.BooleanField(default=True)
    leave_end_date = models.DateField(
        null=True, blank=True,
        help_text='Date when the employee leave (vacation, sick leave, etc) ends')
    rank = models.FloatField(null=True, blank=True)
    hik_person_code = models.CharField(max_length=50, null=True, blank=True)

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'username'
    objects = UserManager()

    def __str__(self):
        if self.status:
            state = self.status.name
        else:
            state = 'Unknown'
        return f'{self.first_name} {self.last_name} - {state}'

    class Meta:
        indexes = [
            models.Index(fields=['username', 'email', 'pinfl', 'tin', 'table_number', 'unique_number', 'phone']),
        ]

    def has_permission(self, method, url_name):
        # Check if the user's role has the permission
        if self.roles.exists():
            for role in self.roles.all():
                if role.permissions.filter(method=method, url_name=url_name).exists():
                    return True

        # Check if the user has any specific permission directly assigned
        if self.permissions.filter(method=method, url_name=url_name).exists():
            return True
        return False

    @property
    def tokens(self):
        refresh = RefreshToken.for_user(self)
        ts = refresh.access_token.payload['exp']
        dt = datetime.fromtimestamp(ts)
        data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'expires_in': str(dt),
        }
        self.last_login = timezone.now()
        self.save()
        return data

    @property
    def mobile_number(self):
        if self.show_mobile_number:
            return self.phone
        return None

    @property
    def is_passcode_set(self):
        return self.passcode is not None

    @property
    def full_name(self):
        if self.father_name:
            return f'{self.last_name} {self.first_name} {self.father_name}'
        return f'{self.last_name} {self.first_name}'

    @property
    def is_user_online(self):
        is_online = redis_client.exists(f'user_{self.id}')
        return bool(is_online)

    def before_save(self):
        if self.color is None:
            self.color = COLORS[random.randrange(0, len(COLORS))]

    def dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'father_name': self.father_name,
            'color': self.color,
            # 'avatar': self.avatar.dict() if self.avatar else None,
            'avatar': None,
            'department': self.department.dict() if self.department else None,
            'position': self.position.dict() if self.position else None,
            'status': self.status.dict() if self.status else None,
            # 'role': self.role.dict() if self.role else None,
            'top_level_department': self.top_level_department.dict() if self.top_level_department else None
        }

    def simple_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'father_name': self.father_name,
            'color': self.color,
            'status': self.status.dict() if self.status else None,
            'avatar': self.avatar.dict() if self.avatar else None,
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'father_name': self.father_name,
            'username': self.username,
            'color': self.color,
            'avatar': self.avatar.dict() if self.avatar else None,
            'position': self.position.dict() if self.position else None,
            'status': self.status.dict() if self.status else None,
            'company': self.company.dict() if self.company else None,
            # 'role': self.role.dict() if self.role else None,
            'top_level_department': self.top_level_department.dict() if self.top_level_department else None
        }

    @property
    def assistant(self):
        user_assistant = self.assistants.filter(is_active=True).first()
        if user_assistant:
            return user_assistant.assistant_id
        return None


class UserDevice(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='devices')
    app_version = models.CharField(max_length=150, null=True, blank=True)
    device_type = models.CharField(max_length=150, null=True, blank=True)
    sim_id = models.CharField(max_length=150, null=True, blank=True)
    device_name = models.CharField(max_length=150, null=True, blank=True)
    product_name = models.CharField(max_length=150, null=True, blank=True)
    wifi_ip = models.CharField(max_length=50, null=True, blank=True)
    trip_verification = models.ForeignKey('compose.TripVerification', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.user.full_name}'


class UserAssistant(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='assistants')
    assistant = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='assistants2')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.id}'


class TopSigner(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='top_signers')
    is_active = models.BooleanField(default=True)
    doc_types = models.ManyToManyField('reference.DocumentType')

    def __str__(self):
        return f'{self.id}'


class SignerModel(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='signers')
    is_active = models.BooleanField(default=True)
    doc_types = models.ManyToManyField('reference.DocumentSubType')

    def __str__(self):
        return f'{self.id}'


class ProjectPermission(BaseModel):
    name = models.CharField(max_length=255, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, null=True, blank=True)
    value = models.CharField(max_length=100, null=True, blank=True)
    method = models.CharField(max_length=100, null=True, blank=True, choices=CONSTANTS.REQUEST_METHODS.CHOICES)
    url_path = models.CharField(max_length=255, null=True, blank=True)
    url_name = models.CharField(max_length=255, null=True, blank=True)
    journal = models.ForeignKey('reference.Journal', on_delete=models.CASCADE, null=True, blank=True)
    document_type = models.ForeignKey('reference.DocumentType', on_delete=models.CASCADE, null=True, blank=True)
    document_sub_type = models.ForeignKey('reference.DocumentSubType', on_delete=models.CASCADE, null=True, blank=True)
    all_visible = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        ordering = ['created_date']


class RoleModel(BaseModel):
    name = models.CharField(max_length=100, null=True)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(ProjectPermission, blank=True)

    def __str__(self):
        return f'{self.name}'

    def dict(self):
        return {
            'id': self.id,
            'name': self.name,
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
        }


class NotificationModel(BaseModel):
    name = models.CharField(max_length=255, null=True)
    description = models.CharField(max_length=500, null=True)
    type = models.CharField(max_length=100, choices=CONSTANTS.NOTIFICATION.TYPES.CHOICES, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class NotificationType(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notification_types')
    notification = models.ForeignKey(NotificationModel, on_delete=models.CASCADE, null=True, blank=True)
    is_mute = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.full_name}'


class MySalary(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='my_salaries')
    pay_name = models.CharField(max_length=500, null=True)
    summ = models.CharField(max_length=50, null=True)
    period = models.CharField(max_length=50, null=True)
    paid = models.CharField(max_length=50, null=True)

    def __str__(self):
        return f'{self.user.full_name}'


class AnnualSalary(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='annual_salaries')
    year = models.CharField(max_length=50, null=True)
    month_value = models.CharField(max_length=50, null=True)
    monthly_salary = models.CharField(max_length=50, null=True)

    def __str__(self):
        return f'{self.user.full_name}'


class UserEquipment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='equipments')
    card_id = models.CharField(max_length=50, null=True)
    name = models.TextField(null=True)
    date_oper = models.CharField(max_length=50, null=True)
    inv_num = models.CharField(max_length=50, null=True)
    qr_text = models.TextField(null=True)
    responsible = models.CharField(null=True, max_length=255)

    def __str__(self):
        return f'{self.user.full_name}'


class BirthdayReaction(BaseModel):
    birthday_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                      null=True, blank=True,
                                      related_name='birthday_reactions')
    reacted_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                   null=True, blank=True,
                                   related_name='given_reactions')
    reaction = models.CharField(max_length=50,
                                null=True, blank=True,
                                choices=CONSTANTS.BIRTHDAY_REACTIONS.CHOICES)

    def __str__(self):
        return f'{self.birthday_user.full_name}'


class BirthdayComment(BaseModel):
    birthday_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='birthday_comments')
    commented_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='given_comments')
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.commented_by.full_name} -> {self.birthday_user.full_name}'


class MoodReaction(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True,
                             related_name='mood_reactions')
    reaction = models.CharField(max_length=50,
                                null=True, blank=True,
                                choices=CONSTANTS.MOOD_REACTIONS.CHOICES)

    def __str__(self):
        return f'{self.user.full_name}'


class CustomAvatar(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True,
                             related_name='avatars')
    file = models.ForeignKey('document.File',
                             on_delete=models.CASCADE,
                             null=True, blank=True)

    def __str__(self):
        return f'{self.file}'


class MySelectedContact(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True,
                             related_name='selected_contacts')
    contact = models.ForeignKey(User, on_delete=models.CASCADE,
                                null=True, blank=True,
                                related_name='selected_by')

    def __str__(self):
        return f'{self.user.full_name}'


class UserFavourite(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="given_favourites"
    )
    favourite_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_favourites"
    )

    class Meta:
        unique_together = ("user", "favourite_user")

    def __str__(self):
        return f"{self.user.full_name} → {self.favourite_user.full_name}"
