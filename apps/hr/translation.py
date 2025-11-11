from modeltranslation.translator import TranslationOptions, translator

from apps.hr.models import WorkSchedule


class WorkScheduleTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(WorkSchedule, WorkScheduleTranslationOptions)
