from modeltranslation.translator import translator, TranslationOptions

from apps.news.models import NewsCategory, NewsTag


class NewsCategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


class NewsTagTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(NewsCategory, NewsCategoryTranslationOptions)
translator.register(NewsTag, NewsTagTranslationOptions)
