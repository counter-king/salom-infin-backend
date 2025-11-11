from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.docflow.filters import DocFlowFilters
from apps.docflow.models import BaseDocument
from apps.docflow.serializers import BaseDocFlowSerializer, ResolutionTreeSerializer
from utils.exception import get_response_message
from utils.utils import build_documents_zip


class DocFlowViewSet(viewsets.ModelViewSet):
    queryset = BaseDocument.objects.order_by('-register_date')
    serializer_class = BaseDocFlowSerializer
    filterset_class = DocFlowFilters

    # permission_classes = (IsUserRequestAllowed,)

    def get_queryset(self):
        q = super(DocFlowViewSet, self).get_queryset()
        return q.order_by('-created_date')

    @action(detail=False, methods=["get"], url_path="download-zip")
    def download_zip(self, request, *args, **kwargs):
        start_date = request.query_params.get("register_start_date")
        end_date = request.query_params.get("register_end_date")
        journal_id = request.query_params.get("journal")

        # filter documents by date range + journal
        documents = BaseDocument.objects.filter(
            register_date__range=[start_date, end_date],
            journal_id=journal_id
        ).prefetch_related("files__file")

        if not documents.exists():
            msg = get_response_message(request, 890)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        return build_documents_zip(documents, journal_id, start_date, end_date)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(methods=['get'], detail=True, url_path='resolution-tree', serializer_class=ResolutionTreeSerializer)
    def resolution_tree(self, request, *args, **kwargs):
        document = self.get_object()
        serializer = ResolutionTreeSerializer(document)
        return Response(serializer.data)
