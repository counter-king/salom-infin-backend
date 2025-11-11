from django.db import models

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class PayrollCategory(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Payroll Category'
        verbose_name_plural = 'Payroll Categories'


class PayrollSubCategory(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(PayrollCategory, related_name='subcategories', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Payroll SubCategory'
        verbose_name_plural = 'Payroll SubCategories'


class Payroll(BaseModel):
    pay_type = models.ForeignKey(PayrollSubCategory, related_name='payrolls', on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey('company.Department', on_delete=models.SET_NULL, null=True)
    sub_department = models.ForeignKey('company.Department', on_delete=models.SET_NULL, null=True,
                                       related_name='sub_department')
    division = models.ForeignKey('company.Department', on_delete=models.SET_NULL, null=True,
                                 related_name='division')
    company = models.ForeignKey('company.Company', on_delete=models.SET_NULL, null=True)
    period = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=30, decimal_places=2)

    def __str__(self):
        return f'{self.pay_type}'


class PayrollPeriod(BaseModel):
    company = models.ForeignKey("company.Company", on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey("company.Department", on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(choices=(("department", "Department"), ("branch", "Branch")),
                            max_length=30,
                            default="department")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    mid_pay_date = models.DateField(null=True, blank=True, help_text="Avans pay date")
    final_pay_date = models.DateField(null=True, blank=True, help_text="Final pay date")
    mid_locked = models.BooleanField(default=False, db_index=True)
    final_locked = models.BooleanField(default=False, db_index=True)
    mid_approved_at = models.DateTimeField(null=True, blank=True)
    final_approved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16,
                              choices=CONSTANTS.ATTENDANCE.PAYROLL_STATUS.CHOICES,
                              default="draft")
    note = models.TextField(blank=True, default="")
    employee_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("company", "department", "year", "month")]
        indexes = [
            models.Index(fields=["company", "year", "month"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.company} {self.year}-{self.month:02d}"


class PayrollRow(BaseModel):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="rows")
    employee = models.ForeignKey("user.User", on_delete=models.PROTECT)
    department = models.ForeignKey("company.Department", on_delete=models.SET_NULL, null=True)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # e.g., 168.00
    total_vacation = models.PositiveSmallIntegerField(default=0)  # days
    total_sick = models.PositiveSmallIntegerField(default=0)
    total_trip = models.PositiveSmallIntegerField(default=0)
    total_absent = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("period", "employee")]
        indexes = [models.Index(fields=["period", "employee"])]

    def __str__(self):
        return f"{self.period} - {self.employee.full_name}"


class PayrollCell(BaseModel):
    """
    One cell per calendar day.
    code: '8', '7', '0', 'm/t', 'k/v', 'x/s', '' ...
    kind: normalized meaning for filtering/analytics.
    """
    KIND = (
        ("work", "Worked"),
        ("vacation", "Vacation"),
        ("sick", "Sick"),
        ("trip", "Business Trip"),
        ("absent", "Absent"),
        ("off", "Weekend/Holiday"),
    )
    row = models.ForeignKey(PayrollRow, on_delete=models.CASCADE, related_name="cells")
    date = models.DateField()  # must belong to the period’s year/month
    code = models.CharField(max_length=8)  # what you display: "8", "7", or user_status.code alias
    kind = models.CharField(max_length=50, choices=KIND, null=True)
    hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # 0..24

    class Meta:
        unique_together = [("row", "date")]
        indexes = [models.Index(fields=["row"]), models.Index(fields=["date"]), models.Index(fields=["kind"])]

    def __str__(self):
        return f"{self.row} {self.date}={self.code}"


class PayrollApproval(models.Model):
    """
    Simple approval flow: one or more approvers to record decisions.
    """
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="approvals")
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    decided = models.BooleanField(default=False)
    approved = models.BooleanField(null=True, blank=True)  # True/False after decide
    note = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.approved}"

    class Meta:
        indexes = [models.Index(fields=["period", "decided"])]
