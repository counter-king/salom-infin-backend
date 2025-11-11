from django.db import models

from base_model.models import BaseModel


class NegotiationType(BaseModel):
    name = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(null=True, blank=True, max_length=255)

    def __str__(self):
        return f'{self.name}'


class NegotiationSubType(BaseModel):
    name = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(null=True, blank=True, max_length=255)
    doc_type = models.ForeignKey(NegotiationType, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class Negotiation(BaseModel):
    """
    Negotiation model
    The documents need to be signed by user periodically
    e.g.
    - Contract
    - Agreement
    - etc.
    """
    title = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    users = models.ManyToManyField('user.User', blank=True)
    doc_type = models.ForeignKey(NegotiationType, on_delete=models.SET_NULL, null=True, blank=True)
    doc_sub_type = models.ForeignKey(NegotiationSubType, on_delete=models.SET_NULL, null=True, blank=True)
    for_new_users = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.id}'


class NegotiationInstance(BaseModel):
    negotiation = models.ForeignKey(Negotiation, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    doc_type = models.ForeignKey(NegotiationType, on_delete=models.SET_NULL, null=True, blank=True)
    doc_sub_type = models.ForeignKey(NegotiationSubType, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.id}'


class Negotiator(BaseModel):
    negotiation = models.ForeignKey(NegotiationInstance,
                                    on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='negotiators')
    user = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    is_signed = models.BooleanField(null=True, blank=True)
    dsi_info = models.TextField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    action_date = models.DateTimeField(null=True, blank=True)
    read_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.id}'
