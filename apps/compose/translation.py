from modeltranslation.translator import translator, TranslationOptions

from apps.compose.models import ComposeStatus, Tag, NegotiationType, NegotiationSubType


class TagTranslationOptions(TranslationOptions):
    fields = ('name',)


class ComposeStatusTranslationOptions(TranslationOptions):
    fields = ('name',)


class NegotiationTypeTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


class NegotiationSubTypeTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(ComposeStatus, ComposeStatusTranslationOptions)
translator.register(Tag, TagTranslationOptions)
translator.register(NegotiationType, NegotiationTypeTranslationOptions)
translator.register(NegotiationSubType, NegotiationSubTypeTranslationOptions)
