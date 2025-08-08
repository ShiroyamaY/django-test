from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tasks.elasticsearch_documents import TaskDocument, CommentDocument
from apps.tasks.serializers import SearchSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter


class SearchView(APIView):
    serializer_class = SearchSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name='target', description='Search target: "task" or "comment"', required=True, type=str),
            OpenApiParameter(name='query', description='Text to search for', required=True, type=str),
        ],
        responses={200: None},
    )
    def get(self, request: Request) -> Response:
        serializer = SearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        target = serializer.data['target']
        query = serializer.data['query']
        search = None

        if target == "task":
            search = TaskDocument.search()
            search = search.query("multi_match", query=query, fields=['title', 'description'])
        elif target == "comment":
            search = CommentDocument.search()
            search = search.query("match", text=query)

        results = search.execute()
        data = [
            {
                **hit.to_dict(),
                "id": hit.meta.id
            }
            for hit in results
        ]

        return Response(data)



