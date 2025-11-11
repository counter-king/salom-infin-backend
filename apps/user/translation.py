from modeltranslation.translator import TranslationOptions, translator

from apps.user.models import UserStatus, NotificationModel, ProjectPermission


class UserStatusTranslationOptions(TranslationOptions):
    fields = ('name',)


class NotificationTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


class ProjectPermissionTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(UserStatus, UserStatusTranslationOptions)
translator.register(NotificationModel, NotificationTranslationOptions)
translator.register(ProjectPermission, ProjectPermissionTranslationOptions)
