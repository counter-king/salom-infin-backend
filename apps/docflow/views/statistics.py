from django.db import connection
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import views
from rest_framework.response import Response

from apps.docflow.serializers.docflow import SimpleResponseSerializer
from utils.constant_ids import get_in_progress_base_doc_status_id, get_completed_base_doc_status_id


class DepartmentStatistics(views.APIView):
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY, description="YYYY-MM-DD", type=openapi.TYPE_STRING)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY, description="YYYY-MM-DD", type=openapi.TYPE_STRING)
    company_id = openapi.Parameter('company_id', openapi.IN_QUERY, description="Company ID", type=openapi.TYPE_INTEGER)

    response = openapi.Response('response description', SimpleResponseSerializer)

    @swagger_auto_schema(manual_parameters=[start_date, end_date, company_id], responses={200: response})
    def get(self, request):
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        company_id = self.request.GET.get('company_id')
        in_progress_status_id = get_in_progress_base_doc_status_id()
        undone_status_id = get_completed_base_doc_status_id()

        query = """
            SELECT
            cd.name as department_name,
            cd.id as department_id,
            count(distinct db.id) as total_documents,
            count(distinct db.id) filter ( where da2.is_read is false ) as unread_documents,
            count(distinct db.id) filter ( where db.status_id = %(in_progress)s ) as in_progress_documents,
            count(distinct db.id) filter ( where db.status_id = %(done)s ) as done_documents
            FROM docflow_basedocument db
            INNER JOIN docflow_reviewer dr on dr.document_id = db.id
            INNER JOIN docflow_assignment da on da.reviewer_id = dr.id
            INNER JOIN docflow_assignee da2 on da2.assignment_id = da.id
            INNER JOIN user_user uu on uu.id = da2.user_id
            INNER JOIN company_department cd on cd.id = uu.top_level_department_id
            AND cd.condition = 'A' and cd.company_id = %(company_id)s
            WHERE db.company_id = %(company_id)s
            AND db.register_date::date BETWEEN %(start_date)s AND %(end_date)s
            GROUP BY cd.name, cd.id
        """

        cursor = connection.cursor()
        params = {
            'in_progress': in_progress_status_id,
            'done': undone_status_id,
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date
        }
        cursor.execute(query, params)
        result = cursor.fetchall()
        data = []
        for row in result:
            data.append({
                'department_name': row[0],
                'department_id': row[1],
                'total_documents': row[2],
                'unread_documents': row[3],
                'in_progress_documents': row[4],
                'done_documents': row[5],
            })

        return Response(data)
