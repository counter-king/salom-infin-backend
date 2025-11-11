from django.contrib.contenttypes.models import ContentType
from rest_framework import permissions

from apps.user.models import ProjectPermission, RoleModel


class IsUserRequestAllowed(permissions.BasePermission):

    def has_permission(self, request, view):
        # if request.user.is_superuser:
        #     return True
        # else:
        method = request.method.upper()
        user = request.user
        role = user.role.id if user.role else None
        model = view.__class__.queryset.model
        path = request.path.split('/')[3]
        content_type = ContentType.objects.get_for_model(model).id
        has_perm = RoleModel.objects.filter(id=role, permissions__content_type_id=content_type,
                                            permissions__methods__overlap=[method],
                                            permissions__url_path=path)
        # print(has_perm.exists())
        return has_perm.exists()
