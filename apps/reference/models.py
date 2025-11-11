import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from base_model.models import BaseModel
from utils.constants import CONSTANTS


# Create your models here.

class CommentModel(BaseModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveBigIntegerField(null=True)
    comment_for = GenericForeignKey('content_type', 'object_id')
    description = models.TextField()
    file = models.ForeignKey("document.File", on_delete=models.SET_NULL, null=True)
    replied_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)

    def __str__(self):
        return '{}'.format(self.object_id)


class StatusModel(BaseModel):
    description = models.CharField(max_length=255, null=True, blank=True)
    group = models.CharField(max_length=30, choices=CONSTANTS.STATUSES.GROUPS.CHOICES)
    is_default = models.BooleanField(default=False)
    is_done = models.BooleanField(default=False)
    is_in_progress = models.BooleanField(default=False)
    is_on_hold = models.BooleanField(default=False)
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    def dict(self):
        return {
            'id': self.id,
            'name': self.name
        }


class Correspondent(BaseModel):
    address = models.CharField(max_length=255, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    checkpoint = models.CharField(max_length=30, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    father_name = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=1, choices=CONSTANTS.GENDER.CHOICES, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    legal_address = models.CharField(max_length=255, null=True, blank=True)
    legal_name = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    pinfl = models.CharField(max_length=30, null=True, blank=True, unique=True)
    tin = models.CharField(max_length=15, null=True, blank=True)
    type = models.CharField(max_length=15, choices=CONSTANTS.CORRESPONDENTS.TYPES.CHOICES)

    def __str__(self):
        return f'{self.name}'


class EmployeeGroup(BaseModel):
    name = models.CharField(max_length=100)
    employees = models.ManyToManyField("user.User")

    # type = models.CharField(max_length=20, choices=CONSTANTS.USER.EMPLOYEE_GROUP.CHOICES,
    #                         default=CONSTANTS.USER.EMPLOYEE_GROUP.PRIVATE)

    def __str__(self):
        return f'{self.name}'


class DocumentTitle(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class ShortDescription(BaseModel):
    title = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.description[:20]}'


class ErrorMessage(BaseModel):
    message = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    status_code = models.CharField(max_length=10)
    code = models.IntegerField(db_index=True, unique=True)

    def __str__(self):
        return f'{self.status_code}'


class FieldActionMapping(BaseModel):
    field_name = models.CharField(max_length=100, unique=True)
    action_code = models.CharField(max_length=10)

    def __str__(self):
        return f'{self.field_name}'


class ActionModel(BaseModel):
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    action = models.CharField(choices=CONSTANTS.ACTIONS.CHOICES, null=True, blank=True, max_length=15)
    description = models.ForeignKey("reference.ActionDescription", on_delete=models.SET_NULL, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveBigIntegerField(null=True)
    history_for = GenericForeignKey('content_type', 'object_id')
    ip_addr = models.CharField(max_length=15, null=True)
    cause_of_deletion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'History for {self.content_type} and {self.object_id}'


class ActionDescription(BaseModel):
    description = models.TextField()
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    icon_name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f'{self.description}'


class Journal(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    icon = models.ForeignKey("document.File", on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)
    is_auto_numbered = models.BooleanField(default=False)
    period_of_time = models.CharField(max_length=10, null=True, blank=True)
    number_of_chars = models.IntegerField(null=True, blank=True)
    prefix = models.CharField(max_length=10, null=True, blank=True)
    index = models.CharField(max_length=10, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_for_compose = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.name}'

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'icon': self.icon.url if self.icon else None,
        }


class DocumentType(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    short_name = models.CharField(max_length=255, null=True, blank=True)
    is_for_compose = models.BooleanField(default=False)
    journal = models.ForeignKey("reference.Journal", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
        }


class DocumentSubType(BaseModel):
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.ForeignKey("reference.DocumentType", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    def as_select_item(self):
        return {
            'id': self.id,
            'name': self.name,
        }


class Country(BaseModel):
    code = models.CharField(max_length=10, null=True, blank=True)
    alpha_2 = models.CharField(max_length=2, null=True, blank=True)
    alpha_3 = models.CharField(max_length=4, null=True, blank=True)
    status = models.CharField(max_length=2, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    currency_code = models.CharField(max_length=5, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name_plural = 'Countries'


class Region(BaseModel):
    country = models.ForeignKey("reference.Country", on_delete=models.SET_NULL, null=True, related_name='regions')
    code = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=255)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class District(BaseModel):
    code = models.CharField(max_length=100, null=True, blank=True)
    region = models.ForeignKey("reference.Region", on_delete=models.SET_NULL, null=True, related_name='districts')
    name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.name}'


class CityDistance(BaseModel):
    from_city = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='distances_from')
    to_city = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='distances_to')
    distance = models.PositiveIntegerField()

    class Meta:
        unique_together = ('from_city', 'to_city')

    def __str__(self):
        return f'Distance from {self.from_city.name} to {self.to_city.name}: {self.distance} km'


class LanguageModel(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class DeliveryType(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class Priority(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Priorities'

    def __str__(self):
        return f'{self.name}'


class DigitalSignInfo(BaseModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    author = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    document_id = models.CharField(max_length=100, null=True)
    content = models.TextField(null=True)
    pkcs7 = models.TextField(null=True)
    pkcs7_info = models.JSONField(null=True)
    signed = models.BooleanField(default=False)
    ip_addr = models.CharField(max_length=255, null=True)
    signed_on = models.CharField(max_length=100, null=True, choices=CONSTANTS.SIGNATURE.SIGN_ON.CHOICES, default='web')
    type = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.uuid}'


class ExpenseType(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class EditableField(BaseModel):
    field_name = models.CharField(max_length=255, null=True, unique=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.field_name}'


class AppVersion(BaseModel):
    type = models.CharField(max_length=20, choices=CONSTANTS.APP_TYPES.CHOICES, unique=True)
    version = models.CharField(max_length=20, null=True, blank=True)
    min_version = models.CharField(max_length=20, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    file = models.ForeignKey('document.MobileApplication', on_delete=models.SET_NULL,
                             null=True, blank=True)

    def __str__(self):
        return f'{self.type}'


class AttendanceReason(BaseModel):
    code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=455)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        ordering = ('-created_date', '-id')


class ExceptionEmployeeQuerySet(models.QuerySet):
    def make_active(self, ids):
        """Bulk activate records by IDs."""
        return self.filter(id__in=ids).update(is_active=True)

    def make_inactive(self, ids, comment=None):
        """
        Bulk deactivate records by IDs — set is_active=False and valid_to=now only for active ones.
        Optionally store a deactivation comment.
        """
        now = timezone.now().date()
        update_data = {
            "is_active": False,
            "valid_to": now,
        }
        if comment:
            update_data["deactivation_comment"] = comment

        return self.filter(id__in=ids, is_active=True).update(**update_data)


class ExceptionEmployeeManager(models.Manager):
    def get_queryset(self):
        """Return a custom queryset to enable queryset methods via objects."""
        return ExceptionEmployeeQuerySet(self.model, using=self._db)

    def process_user_exceptions(self, user_ids, comment=None):
        """
        For each user:
          - If the user already has an active record, skip.
          - Otherwise:
              * Deactivate any currently active records (if any).
              * Create a new active record with an optional activation comment.
        Returns the list of newly created instances.
        """
        now = timezone.now().date()
        created_instances = []

        for user_id in user_ids:
            # Skip if there is already an active record for this user
            if self.filter(user_id=user_id, is_active=True).exists():
                continue

            # Deactivate any previously active records just in case
            self.filter(user_id=user_id, is_active=True).update(
                is_active=False,
                valid_to=now,
                deactivation_comment="Automatically deactivated during new assignment",
            )

            # Create a new active record with activation comment
            new_instance = self.create(
                user_id=user_id,
                is_active=True,
                valid_from=now,
                valid_to=None,
                activation_comment=comment,
            )
            created_instances.append(new_instance)

        return created_instances


class ExceptionEmployee(BaseModel):
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    activation_comment = models.TextField(null=True, blank=True)
    deactivation_comment = models.TextField(null=True, blank=True)

    objects = ExceptionEmployeeManager.from_queryset(ExceptionEmployeeQuerySet)()

    class Meta:
        ordering = ('-is_active', '-created_date', '-id',)
        verbose_name = "Exception employee"
        verbose_name_plural = "Exception employees"

    def __str__(self):
        return f"{self.user.full_name}"
