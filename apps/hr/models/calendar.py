from django.db import models

from base_model.models import BaseModel


class YearModel(BaseModel):
    year = models.IntegerField(default=0, unique=True, db_index=True)

    def __str__(self):
        return f'{self.year}'


class IABSCalendar(BaseModel):
    year = models.ForeignKey(YearModel, on_delete=models.CASCADE, related_name='months')
    work_day = models.IntegerField(default=0)
    date = models.DateField()
    is_holiday = models.BooleanField(default=False)
    holiday_name = models.CharField(max_length=255, null=True, blank=True)
    holiday_name_ru = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.date}'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["year", "date"],
                name="uniq_iabscalendar_year_date",
            ),
        ]
        indexes = [
            models.Index(fields=["year", "date"]),
            models.Index(fields=["date"]),
        ]
