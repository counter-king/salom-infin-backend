from django.db import models

from base_model.models import BaseModel


class Company(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)
    local_code = models.CharField(max_length=10, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=25, null=True, blank=True)
    condition = models.CharField(max_length=10, null=True, blank=True)
    region = models.ForeignKey('reference.Region', on_delete=models.SET_NULL, null=True, blank=True)
    env_id = models.CharField(max_length=50, null=True, blank=True)
    is_main = models.BooleanField(default=False)

    class Meta:
        db_table = 'company'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return f"{self.name} - {self.local_code}"


class Position(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    iabs_post_id = models.IntegerField(null=True, blank=True)
    iabs_level_code = models.CharField(max_length=20, null=True, blank=True)
    condition = models.CharField(max_length=10, null=True, blank=True, default='A')

    def __str__(self):
        return f'{self.name}'

    def dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
        }


class Department(BaseModel):
    iabs_dept_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    parent_code = models.CharField(max_length=255, null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='departments')
    condition = models.CharField(max_length=10, null=True, blank=True, default='A')
    level = models.IntegerField(default=0)
    sub_department_count = models.IntegerField(default=0)
    hik_org_code = models.CharField(max_length=50, null=True, blank=True, unique=True)
    dep_index = models.PositiveIntegerField(null=True, blank=True, unique=True)

    def __str__(self):
        return self.name


class EnvModel(BaseModel):
    name_uz = models.CharField(max_length=255, null=True, blank=True)
    name_ru = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=50, null=True, blank=True)
    company_logo = models.TextField(null=True, blank=True)
    logo_size = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.code
