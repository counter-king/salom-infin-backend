import re
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q
from rest_framework import views, generics, permissions
from rest_framework.response import Response
from django.urls import URLResolver, URLPattern

from apps.docflow.models import Assignee, Reviewer
from apps.compose.models import Signer, Approver, Negotiator
from apps.user.models import User
from base_model.serializers import DashboardUserSerializer
from utils.constant_ids import get_compose_status_id, get_completed_base_doc_status_id, user_search_status_ids
from utils.constants import CONSTANTS


class MockTestView(views.APIView):
    permission_classes = [permissions.AllowAny, ]

    def post(self, request, *args, **kwargs):
        return Response({'status': 'success'})


class UnreadCountViewSet(views.APIView):
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        excluded_types = [
            CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
            CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2,
        ]
        user_or_assistant = Q(user_id=user_id)  # | Q(user__assistants__assistant_id=user_id)
        unread_for_review = Reviewer.objects.filter(user_or_assistant & Q(is_read=False)).count()
        unread_assignments = Assignee.objects.filter(
            user_or_assistant & Q(is_read=False) & Q(assignment__is_verified=True)).count()
        for_signature = Signer.objects.filter(
            user_or_assistant & Q(is_signed__isnull=True) & Q(compose__status__is_draft=False) & Q(
                is_all_approved=True) & ~Q(compose__document_sub_type_id__in=excluded_types)).count()
        for_approval = Approver.objects.filter(
            user_or_assistant & Q(is_approved__isnull=True) & Q(compose__status__is_draft=False) & ~Q(compose__document_sub_type_id__in=excluded_types)).count()

        # negotiator unread counts
        unread_negotiator_count = Negotiator.objects.filter(user_id=user_id, is_signed=None).count()

        unread_count = {
            'all': unread_for_review + unread_assignments + for_signature + for_approval,
            'unread_for_review': unread_for_review,
            'unread_assignments': unread_assignments,
            'for_signature': for_signature,
            'for_approval': for_approval,
        }

        hr_unread_count = {
            'all': unread_negotiator_count,
            'unread_negotiator': unread_negotiator_count
        }

        return Response({'boxes': unread_count, 'hr': hr_unread_count})


class DashboardUserList(generics.ListAPIView):
    serializer_class = DashboardUserSerializer
    search_fields = ['first_name', 'last_name', 'father_name', 'normalized_cisco', 'cisco']

    def get_queryset(self):
        """
        This function returns all users
        """

        status_ids = user_search_status_ids()
        return User.objects.filter(status_id__in=status_ids)


class ListAllUrlsView(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        urls = self.get_all_urls()
        # grouped_urls = self.group_urls_by_module(urls)
        return Response(urls)

    # List of URL patterns to exclude
    EXCLUDE_PATTERNS = ['admin', 'auth', 'static', 'media', 'swagger', 'redoc', 'api-auth', 'login', 'api-root']

    def get_all_urls(self, urlpatterns=None, parent_pattern=''):
        if urlpatterns is None:
            from config.urls import urlpatterns  # Import the root URL patterns

        url_list = []

        for pattern in urlpatterns:

            # Skip URLs that match any of the excluded patterns
            if isinstance(pattern, URLPattern) and self.should_skip_url(pattern.pattern):
                continue

            if isinstance(pattern, URLPattern):
                # Handling basic URL pattern (e.g., /api/users/)
                full_pattern = parent_pattern + str(pattern.pattern)
                clean_url = self.clean_url(full_pattern)
                content_type = self.get_model_content_type(pattern)

                url_list.append({
                    'url': clean_url,
                    'name': pattern.name,
                    'content_type': content_type,
                })

            elif isinstance(pattern, URLResolver):
                # Handling included URL patterns

                if self.should_skip_url(pattern.pattern):
                    continue

                full_pattern = parent_pattern + str(pattern.pattern)
                url_list.extend(self.get_all_urls(pattern.url_patterns, full_pattern))

        return url_list

    def clean_url(self, url):
        """
        Clean the URL by removing regex characters and unnecessary slashes.
        """
        # Remove regex-related characters (^, $, \)
        url = re.sub(r'\^|\$|\\', '', url)
        # Remove duplicate slashes
        url = re.sub(r'//+', '/', url)
        return url

    def get_model_content_type(self, pattern):
        """
        Try to retrieve the model's content type ID from the viewset.
        """

        def get_content_type(model):
            """
            Retrieve the content type ID for a given model.
            """
            return ContentType.objects.get_for_model(model).id

        callback = pattern.callback
        try:
            if hasattr(callback, 'cls') and hasattr(callback.cls, 'queryset'):
                model = callback.cls.queryset.model
                return get_content_type(model)
            elif hasattr(callback, 'cls') and hasattr(callback.cls, 'get_queryset'):
                model = callback.cls().get_queryset().model
                return get_content_type(model)
        except Exception as e:
            pass
        return None  # Fallback to None if no model found

    def should_skip_url(self, pattern):
        """
        Determines whether the URL pattern should be skipped based on the EXCLUDE_PATTERNS list.
        """
        pattern_str = str(pattern)
        # Check if any of the excluded patterns are in the current URL pattern
        return any(excluded in pattern_str for excluded in self.EXCLUDE_PATTERNS)

    def group_urls_by_module(self, url_list):
        """
        Groups URLs by their app/module.
        """
        grouped_urls = defaultdict(list)

        for url_info in url_list:
            # Group by the module part of the view name
            module_name = url_info['model'] or 'unknown'  # Group by model name or 'unknown'
            grouped_urls[module_name].append(url_info)

        return grouped_urls


class NewCountsView(views.APIView):
    excluded = (
        CONSTANTS.DOC_TYPE_ID.EXTEND_TRIP_DECREE_V2,
        CONSTANTS.DOC_TYPE_ID.TRIP_DECREE_V2,
    )

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        context = {
            'for_review': self.new_for_review_count(user_id),
            'assignments': self.new_assignments_count(user_id),
            'for_signature': self.new_for_signature_count(user_id),
            'for_approval': self.new_for_approval_count(user_id)
        }
        return Response(context)

    def new_for_review_count(self, user_id):
        query = """
        SELECT COUNT(*) FROM docflow_reviewer
        WHERE user_id = %(user_id)s AND is_read = FALSE
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def new_assignments_count(self, user_id):
        query = """
        SELECT COUNT(*) FROM docflow_assignee da
        INNER JOIN docflow_assignment da2 ON da.assignment_id = da2.id AND da2.is_verified = TRUE
        WHERE da.user_id = %(user_id)s AND da.is_read = FALSE 
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def new_for_signature_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = f"""
                SELECT COUNT(*) 
                FROM compose_signer cs
                INNER JOIN compose_compose cc 
                    ON cs.compose_id = cc.id 
                    AND cc.is_deleted = FALSE 
                    AND cc.status_id <> %(draft_status_id)s
                WHERE cs.user_id = %(user_id)s
                  AND cs.is_signed IS NULL
                  AND cs.is_all_approved = TRUE
                  AND cc.document_sub_type_id NOT IN {self.excluded}
            """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def new_for_approval_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = f"""
        SELECT COUNT(*) FROM compose_approver ca
        INNER JOIN compose_compose cc ON ca.compose_id = cc.id AND cc.is_deleted = FALSE AND cc.status_id <> %(draft_status_id)s
        WHERE ca.user_id = %(user_id)s 
        AND ca.is_approved IS NULL
        AND cc.document_sub_type_id NOT IN {self.excluded}
        """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]


class InProgressCountsView(views.APIView):
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        context = {
            'for_review': self.in_progress_for_review_count(user_id),
            'assignments': self.in_progress_assignments_count(user_id),
            'for_signature': self.in_progress_for_signature_count(user_id),
            'for_approval': self.in_progress_for_approval_count(user_id)
        }
        return Response(context)

    def in_progress_for_review_count(self, user_id):
        done_status_id = get_completed_base_doc_status_id()
        query = """
        SELECT COUNT(*) FROM docflow_reviewer
        WHERE user_id = %(user_id)s AND is_read = TRUE 
        AND has_resolution = FALSE
        AND status_id <> %(done_status_id)s
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id,
            'done_status_id': done_status_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def in_progress_assignments_count(self, user_id):
        done_status_id = get_completed_base_doc_status_id()
        query = """
        SELECT COUNT(*) FROM docflow_assignee da
        INNER JOIN docflow_assignment da2 ON da.assignment_id = da2.id AND da2.is_verified = TRUE
        WHERE da.user_id = %(user_id)s AND da.is_read = TRUE 
        AND da.status_id <> %(done_status_id)s
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id,
            'done_status_id': done_status_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def in_progress_for_signature_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = """
        SELECT COUNT(*) FROM compose_signer cs
        INNER JOIN compose_compose cc ON cs.compose_id = cc.id AND cc.is_deleted = FALSE AND cc.status_id <> %(draft_status_id)s
        WHERE cs.user_id = %(user_id)s 
        AND cs.is_signed IS FALSE 
        AND cs.is_all_approved = TRUE
        """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def in_progress_for_approval_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = """
        SELECT COUNT(*) FROM compose_approver ca
        INNER JOIN compose_compose cc ON ca.compose_id = cc.id AND cc.is_deleted = FALSE AND cc.status_id <> %(draft_status_id)s
        WHERE ca.user_id = %(user_id)s 
        AND ca.is_approved IS FALSE
        """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]


class AllCountsView(views.APIView):
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        context = {
            'for_review': self.all_for_review_count(user_id),
            'assignments': self.all_assignments_count(user_id),
            'for_signature': self.all_for_signature_count(user_id),
            'for_approval': self.all_for_approval_count(user_id)
        }
        return Response(context)

    def all_for_review_count(self, user_id):
        query = """
        SELECT COUNT(*) FROM docflow_reviewer
        WHERE user_id = %(user_id)s
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def all_assignments_count(self, user_id):
        query = """
        SELECT COUNT(*) FROM docflow_assignee da
        INNER JOIN docflow_assignment da2 ON da.assignment_id = da2.id AND da2.is_verified = TRUE
        WHERE da.user_id = %(user_id)s
        """
        cursor = connection.cursor()
        params = {
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def all_for_signature_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = """
        SELECT COUNT(*) FROM compose_signer cs
        INNER JOIN compose_compose cc ON cs.compose_id = cc.id AND cc.is_deleted = FALSE AND cc.status_id <> %(draft_status_id)s
        WHERE cs.user_id = %(user_id)s 
        AND cs.is_all_approved = TRUE
        """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def all_for_approval_count(self, user_id):
        draft_status_id = get_compose_status_id(type='draft')
        query = """
        SELECT COUNT(*) FROM compose_approver ca
        INNER JOIN compose_compose cc ON ca.compose_id = cc.id AND cc.is_deleted = FALSE AND cc.status_id <> %(draft_status_id)s
        WHERE ca.user_id = %(user_id)s 
        """
        cursor = connection.cursor()
        params = {
            'draft_status_id': draft_status_id,
            'user_id': user_id
        }
        cursor.execute(query, params)
        return cursor.fetchone()[0]


class UnreadChatsCountView(views.APIView):
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        query = """
            SELECT COUNT(DISTINCT m.chat_id) AS unread_chat_count
            FROM wchat_messagereceiver mr
                JOIN wchat_chatmessage m ON m.id = mr.message_id and m.deleted = FALSE
                JOIN wchat_chat c ON c.id = m.chat_id AND c.deleted = FALSE
            WHERE mr.receiver_id = %(user_id)s AND mr.read IS NULL
        """
        with connection.cursor() as cursor:
            cursor.execute(query, {'user_id': user_id})
            result = cursor.fetchone()[0] or 0  # Ensure a valid number

        return Response({'count': result})
