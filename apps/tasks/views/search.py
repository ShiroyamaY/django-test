from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tasks.documents import CommentDocument, TaskDocument
from apps.tasks.serializers import SearchSerializer


class SearchView(APIView):
    serializer_class = SearchSerializer

    def get_search(self, target: str, query: str):
        if target == "task":
            search = TaskDocument.search()
            return search.query("multi_match", query=query, fields=["title", "description"])
        elif target == "comment":
            search = CommentDocument.search()
            return search.query("match", text=query)
        else:
            return None

    @extend_schema(
        parameters=[
            OpenApiParameter(name="target", description='Search target: "task" or "comment"', required=True, type=str),
            OpenApiParameter(name="query", description="Text to search for", required=True, type=str),
        ],
        responses={200: None, 400: None},
    )
    def get(self, request: Request) -> Response:
        serializer = SearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target"]
        query = serializer.validated_data["query"]

        search = self.get_search(target, query)
        if not search:
            return Response({"detail": "Invalid target parameter"}, status=status.HTTP_400_BAD_REQUEST)

        results = search.execute()
        data = [{**hit.to_dict(), "id": hit.meta.id} for hit in results]

        return Response(data)
