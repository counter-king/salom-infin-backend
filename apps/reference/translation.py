from modeltranslation.translator import TranslationOptions, translator

from apps.reference.models import (
    ActionDescription,
    DeliveryType,
    DocumentTitle,
    District,
    DocumentType,
    DocumentSubType,
    ErrorMessage,
    Journal,
    LanguageModel,
    Priority,
    Region,
    ShortDescription,
    StatusModel,
    ExpenseType,
    AttendanceReason,
)


class ActionDescriptionTranslationOptions(TranslationOptions):
    fields = ('description',)


class StatusTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


class ErrorMessageTranslationOptions(TranslationOptions):
    fields = ('message',)


class ShortDescriptionTranslationOptions(TranslationOptions):
    fields = ('description',)


class RegionTranslationOptions(TranslationOptions):
    fields = ('name',)


class DistrictTranslationOptions(TranslationOptions):
    fields = ('name',)


class LanguageModelTranslationOptions(TranslationOptions):
    fields = ('name',)


class DeliveryTypeTranslationOptions(TranslationOptions):
    fields = ('name',)


class PriorityTranslationOptions(TranslationOptions):
    fields = ('name',)


class JournalTranslationOptions(TranslationOptions):
    fields = ('name',)


class DocumentTypeTranslationOptions(TranslationOptions):
    fields = ('name',)


class DocumentSubTypeTranslationOptions(TranslationOptions):
    fields = ('name',)


class DocumentTitleTranslationOptions(TranslationOptions):
    fields = ('name',)


class ExpenseTypeTranslationOptions(TranslationOptions):
    fields = ('name',)

class AttendanceReasonTranslationOptions(TranslationOptions):
    fields = ('name', 'description',)




translator.register(ActionDescription, ActionDescriptionTranslationOptions)
translator.register(DocumentTitle, DocumentTitleTranslationOptions)
translator.register(StatusModel, StatusTranslationOptions)
translator.register(ErrorMessage, ErrorMessageTranslationOptions)
translator.register(ShortDescription, ShortDescriptionTranslationOptions)
translator.register(Region, RegionTranslationOptions)
translator.register(District, DistrictTranslationOptions)
translator.register(LanguageModel, LanguageModelTranslationOptions)
translator.register(DeliveryType, DeliveryTypeTranslationOptions)
translator.register(Priority, PriorityTranslationOptions)
translator.register(Journal, JournalTranslationOptions)
translator.register(DocumentType, DocumentTypeTranslationOptions)
translator.register(DocumentSubType, DocumentSubTypeTranslationOptions)
translator.register(ExpenseType, ExpenseTypeTranslationOptions)
translator.register(AttendanceReason, AttendanceReasonTranslationOptions)
