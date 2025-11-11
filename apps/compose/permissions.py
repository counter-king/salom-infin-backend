from django.db.models import Q
from rest_framework.permissions import BasePermission

from apps.user.models import ProjectPermission


class ComposePermission(BasePermission):

    def has_permission(self, request, view):
        """
        Check for general permissions based on the user's permissions.
        """
        user = request.user
        method = request.method

        if user.permissions.filter(method=method, content_type_id=30).exists():
            return True

        # If none of the above permissions are granted, deny access
        return False

    def has_object_permission(self, request, view, obj):
        """
        Check object-level permissions based on the ComposeModel instance and the user's permissions.
        """
        user = request.user
        method = request.method

        # Always allow the author to access their own ComposeModel
        if user == obj.author:
            print('author ', True)
            return True

        # Fetch permissions in order of hierarchy: doc_sub_type -> doc_type -> journal
        # permissions = ProjectPermission.objects.filter(
        #     content_type__model='composemodel'
        # )

        # Check for specific doc_sub_type permission
        if user.permissions.filter(document_sub_type=obj.document_sub_type, method=method).exists():
            print('doc_sub_type ', True)
            return True

        # Check for doc_type permission if no specific doc_sub_type permission is found
        if user.permissions.filter(document_type=obj.document_type,
                                   document_sub_type__isnull=True,
                                   method=method).exists():
            print('doc_type ', True)
            return True

        # Check for general journal permission if no doc_type or doc_sub_type permission is found
        if user.permissions.filter(journal=obj.journal,
                                   document_type__isnull=True,
                                   document_sub_type__isnull=True,
                                   method=method).exists():
            print('journal ', True)
            return True

        # If none of the above permissions are granted, deny access
        return False
