from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class Receiver(BaseModel):
    type = models.CharField(max_length=100, null=True, blank=True, choices=CONSTANTS.COMPOSE.RECEIVERS.CHOICES)
    companies = models.ManyToManyField('company.Company', blank=True)
    departments = models.ManyToManyField('company.Department', blank=True)
    organizations = models.ManyToManyField('reference.Correspondent', blank=True)

    def __str__(self):
        return f'{self.id}'


class ComposeStatus(BaseModel):
    name = models.CharField(max_length=50, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    is_approve = models.BooleanField(default=False)
    declined_from_approver = models.BooleanField(default=False)
    declined_from_signer = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Compose Statuses'


class Tag(BaseModel):
    name = models.CharField(max_length=100, null=True, blank=True)
    document_sub_type = models.ForeignKey('reference.DocumentSubType', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class Compose(BaseModel):
    author = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='author'
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    content = models.TextField(null=True, blank=True)
    curator = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='curator'
    )
    document_type = models.ForeignKey(
        'reference.DocumentType',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    document_sub_type = models.ForeignKey(
        'reference.DocumentSubType',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    files = models.ManyToManyField('document.File', blank=True)
    file = models.ForeignKey(
        'document.File',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text='After signing, the file will be saved as pdf'
    )
    journal = models.ForeignKey(
        'reference.Journal',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='children'
    )
    receiver = models.ForeignKey(Receiver, on_delete=models.SET_NULL, null=True, blank=True)
    register_date = models.DateTimeField(null=True, blank=True)
    register_number = models.CharField(max_length=20, null=True, blank=True)
    register_number_int = models.IntegerField(default=0)
    registered_document = models.ForeignKey(
        'docflow.BaseDocument',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registered_document'
    )
    replied_document = models.ForeignKey(
        'docflow.BaseDocument',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='replied_document'
    )
    sender = models.ForeignKey('company.Department', on_delete=models.SET_NULL, null=True, blank=True)
    short_description = models.TextField(null=True, blank=True)
    status = models.ForeignKey(
        ComposeStatus,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    title = models.ForeignKey(
        'reference.DocumentTitle',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    check_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    is_deleted = models.BooleanField(default=False)
    is_signed = models.BooleanField(default=False)
    signed_date = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    user = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='user',
        help_text="For attorney documents and etc."
    )
    start_date = models.DateField(null=True, blank=True,
                                  help_text='Attorney document start date')
    end_date = models.DateField(null=True, blank=True,
                                help_text='Attorney document end date')
    trip_notice_id = models.PositiveIntegerField(null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.document_type.name} - {self.register_number}'

    def as_select_item(self):
        return {
            'id': self.id,
            'journal': self.journal.as_select_item() if self.journal else None,
            'document_type': self.document_type.as_select_item() if self.document_type else None,
            'document_sub_type': self.document_sub_type.as_select_item() if self.document_sub_type else None,
        }


class ComposeLink(BaseModel):
    from_compose = models.ForeignKey(
        Compose,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='from_compose_links'
    )
    to_compose = models.ForeignKey(
        Compose,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='to_compose_links'
    )
    link_type = models.CharField(
        max_length=100,
        null=True,
        choices=CONSTANTS.COMPOSE.LINK_TYPES.CHOICES,
        default=CONSTANTS.COMPOSE.LINK_TYPES.DEFAULT
    )

    def __str__(self):
        return f'{self.link_type}'


class Approver(BaseModel):
    compose = models.ForeignKey(Compose, on_delete=models.CASCADE, null=True, blank=True, related_name='approvers')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    added_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='added_approvers')
    is_approved = models.BooleanField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    action_date = models.DateTimeField(null=True, blank=True)
    read_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.id}'


class Signer(BaseModel):
    compose = models.ForeignKey(Compose, on_delete=models.CASCADE,
                                null=True, blank=True, related_name='signers')
    deadline = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    is_signed = models.BooleanField(null=True, blank=True)
    type = models.CharField(null=True, blank=True, max_length=100,
                            choices=CONSTANTS.COMPOSE.SIGNER_TYPES.CHOICES,
                            default=CONSTANTS.COMPOSE.SIGNER_TYPES.DEFAULT)
    comment = models.TextField(null=True, blank=True)
    performers = models.JSONField(null=True, blank=True)
    resolution_text = models.TextField(null=True, blank=True)
    resolution_type = models.CharField(max_length=20, null=True, blank=True)
    is_all_approved = models.BooleanField(null=True, blank=True)
    action_date = models.DateTimeField(null=True, blank=True)
    certificate_info = models.TextField(null=True, blank=True)
    pkcs7 = models.TextField(null=True, blank=True)
    read_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.id}'


class ComposeVersionModel(BaseModel):
    old_text = models.TextField(null=True)
    new_text = models.TextField(null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveBigIntegerField(null=True)
    history_for = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f'History for {self.content_type} and {self.object_id}'

    @classmethod
    def create_history(cls, old_text: str, new_text: str, history_for, user_id):
        cls(
            old_text=old_text,
            new_text=new_text,
            history_for=history_for,
            created_by_id=user_id
        ).save()


class IABSActionHistory(BaseModel):
    compose = models.ForeignKey(Compose, on_delete=models.SET_NULL, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveBigIntegerField(null=True)
    history_for = GenericForeignKey('content_type', 'object_id')
    result = models.TextField(null=True, blank=True)
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(choices=CONSTANTS.COMPOSE.IABS_ACTIONS.CHOICES)
    action = models.CharField(choices=CONSTANTS.COMPOSE.IABS_ACTIONS.CHOICES,
                              default=CONSTANTS.COMPOSE.IABS_ACTIONS.DEFAULT)
    type = models.CharField(choices=CONSTANTS.COMPOSE.IABS_ACTION_TYPES.CHOICES,
                            max_length=100, null=True)
    iabs_id = models.PositiveBigIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=100, null=True, blank=True)
    request_body = models.JSONField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    endpoint = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.status} - {self.object_id}'

    @classmethod
    def create_history(cls, status: str, history_for,
                       action, compose_id=None,
                       result: str = None, user_id=None, iabs_id=None,
                       request_body: dict = None, response_body: dict = None,
                       endpoint: str = None, type: str = None, request_id: str = None):
        cls(
            status=status,
            history_for=history_for,
            result=result,
            user_id=user_id,
            iabs_id=iabs_id,
            action=action,
            compose_id=compose_id,
            request_body=request_body,
            response_body=response_body,
            endpoint=endpoint,
            type=type,
            request_id=request_id
        ).save()

    class Meta:
        verbose_name = 'IABS Action History'
        verbose_name_plural = 'IABS Action Histories'


class IABSRequestCallHistory(BaseModel):
    action_history = models.ForeignKey(
        IABSActionHistory,
        on_delete=models.CASCADE,
        related_name='request_call_histories',
        null=True, blank=True
    )
    caller = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    requested_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(choices=CONSTANTS.COMPOSE.IABS_ACTIONS.CHOICES)
    request_id = models.CharField(max_length=100, null=True, blank=True)
    request_body = models.JSONField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_text = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.caller}'
