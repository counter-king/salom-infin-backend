from django.db import models

from base_model.models import BaseModel


class RegCounter(models.Model):
    journal = models.ForeignKey("reference.Journal", on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()  # e.g., 2025
    next_no = models.PositiveIntegerField(default=1)  # next order to allocate

    class Meta:
        unique_together = [("journal", "year")]
        indexes = [models.Index(fields=["journal", "year"])]


class BaseDocumentManager(models.Manager):
    def get_queryset(self):
        return super(BaseDocumentManager, self).get_queryset().filter(is_deleted=False)


class BaseDocument(BaseModel):
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.ForeignKey("reference.StatusModel", on_delete=models.SET_NULL, null=True, blank=True)
    delivery_type = models.ForeignKey("reference.DeliveryType", on_delete=models.SET_NULL, null=True, blank=True)
    priority = models.ForeignKey("reference.Priority", on_delete=models.SET_NULL, null=True, blank=True)
    document_type = models.ForeignKey("reference.DocumentType", on_delete=models.SET_NULL, null=True, blank=True)
    document_sub_type = models.ForeignKey("reference.DocumentSubType", on_delete=models.SET_NULL, null=True, blank=True)
    correspondent = models.ForeignKey("reference.Correspondent", on_delete=models.SET_NULL, null=True, blank=True)
    journal = models.ForeignKey("reference.Journal", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("reference.LanguageModel", on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    grif = models.CharField(max_length=20, null=True, blank=True)
    register_date = models.DateField(null=True, blank=True)
    register_number = models.CharField(max_length=20, null=True, blank=True)
    outgoing_number = models.CharField(max_length=20, null=True, blank=True)
    outgoing_date = models.DateField(null=True, blank=True)
    number_of_papers = models.IntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    company = models.ForeignKey("company.Company", on_delete=models.SET_NULL, null=True, blank=True)
    compose = models.ForeignKey("compose.Compose", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.register_number}'

    def as_select_item(self):
        return {
            'id': self.id,
            'register_number': self.register_number,
        }


class DocumentFile(BaseModel):
    document = models.ForeignKey("docflow.BaseDocument", on_delete=models.CASCADE, related_name="files", null=True,
                                 blank=True)
    file = models.ForeignKey("document.File", on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f'{self.document}'


class Reviewer(BaseModel):
    document = models.ForeignKey("docflow.BaseDocument",
                                 on_delete=models.CASCADE,
                                 related_name="reviewers",
                                 null=True, blank=True)
    user = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey("reference.StatusModel", on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    has_resolution = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    read_time = models.DateTimeField(null=True, blank=True)
    files = models.ManyToManyField("document.File", blank=True)

    def __str__(self):
        return f'{self.id}'

    def dict(self):
        return {
            'id': self.id,
            'user': self.user.as_select_item() if self.user else None,
            'status': self.status.dict() if self.status else None,
            'comment': self.comment,
            'has_resolution': self.has_resolution,
            'is_read': self.is_read,
            'read_time': self.read_time,
        }

    def as_select_item(self):
        return {
            'id': self.id,
            'user': self.user.as_select_item() if self.user else None,
            'status': self.status.dict() if self.status else None,
            'comment': self.comment,
            'has_resolution': self.has_resolution,
            'is_read': self.is_read,
            'read_time': self.read_time,
        }


class Assignment(BaseModel):
    reviewer = models.ForeignKey("docflow.Reviewer", on_delete=models.CASCADE, related_name="assignments")
    content = models.TextField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=20, null=True, blank=True)
    is_project_resolution = models.BooleanField(default=False)
    has_child_resolution = models.BooleanField(default=False)
    receipt_date = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return f'{self.type}'

    def dict(self):
        return {
            'id': self.id,
            'reviewer': self.reviewer.as_select_item() if self.reviewer else None,
            'content': self.content,
            'deadline': self.deadline,
            'type': self.type,
            'is_project_resolution': self.is_project_resolution,
            'has_child_resolution': self.has_child_resolution,
            'receipt_date': self.receipt_date,
            'is_verified': self.is_verified
        }


class Assignee(BaseModel):
    assignment = models.ForeignKey("docflow.Assignment", on_delete=models.CASCADE,
                                   related_name="assignees", null=True,
                                   blank=True)
    content = models.TextField(null=True, blank=True)
    files = models.ManyToManyField("document.File", blank=True)
    is_controller = models.BooleanField(default=False)
    is_performed = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    is_responsible = models.BooleanField(default=False)
    performed_date = models.DateTimeField(null=True, blank=True)
    read_time = models.DateTimeField(null=True, blank=True)
    status = models.ForeignKey("reference.StatusModel", on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return f'{self.user.full_name}'

    class Meta:
        ordering = ['-is_responsible']


class InboxItem(BaseModel):
    """
    Denormalized fast list:
      - to_acquaint  : reviewers/assistants before any resolution exists
      - to_review    : reviewers/assistants on a draft root resolution (verify)
      - to_assign    : (optional) managers/assistants while preparing performers
      - to_execute   : performers with visible assignments
    """
    user = models.ForeignKey("user.User", on_delete=models.CASCADE)
    document = models.ForeignKey(BaseDocument, on_delete=models.CASCADE)
    kind = models.CharField(max_length=24)  # to_acquaint|to_review|to_assign|to_execute
    review = models.ForeignKey("docflow.Reviewer", on_delete=models.SET_NULL, null=True, blank=True)
    assignment = models.ForeignKey(Assignment, null=True, blank=True, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    read_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_read", "created_date"]),
            models.Index(fields=["user", "kind", "created_date"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "document", "kind"], name="uniq_inbox_user_doc_kind"),
        ]
