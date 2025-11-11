from modeltranslation.translator import TranslationOptions, translator

from apps.company.models import Company, Position, Department


class CompanyTranslationOptions(TranslationOptions):
    fields = ('name', 'address')


class PositionTranslationOptions(TranslationOptions):
    fields = ('name',)


class DepartmentTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Company, CompanyTranslationOptions)
translator.register(Position, PositionTranslationOptions)
translator.register(Department, DepartmentTranslationOptions)
