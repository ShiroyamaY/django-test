import uuid

from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from django_filters.rest_framework import DjangoFilterBackend
from django_minio_backend import MinioBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.common.authentication import MinioWebhookAuthentication
from apps.common.helpers import get_previous_month_range_utc
from apps.common.views import MultiSerializerMixin
from apps.tasks.documents import CommentDocument, TaskDocument
from apps.tasks.models import Attachment, Comment, Task, TimeLog
from apps.tasks.serializers import (
    AttachmentListSerializer,
    AttachmentPresignUrlSerializer,
    CommentCreateSerializer,
    CommentRetrieveSerializer,
    SearchSerializer,
    TaskAssignUserSerializer,
    TaskCompleteSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskRetrieveSerializer,
    TaskUpdateSerializer,
    TimeLogSerializer,
    TimeLogSpecificDateSerializer,
    TimeLogStartSerializer,
    TimeLogStopSerializer,
    TopTaskSerializer,
)
from apps.tasks.signals import task_completed
from config.settings import (
    CACHE_TIMEOUTS,
    MINIO_ATTACHMENTS_BUCKET,
    MINIO_URL_EXPIRY_HOURS,
)


class TaskView(MultiSerializerMixin, ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskRetrieveSerializer
    permission_classes = [IsAuthenticated]
    multi_serializer_class = {
        "create": TaskCreateSerializer,
        "assign_user": TaskAssignUserSerializer,
        "update": TaskUpdateSerializer,
        "complete": TaskCompleteSerializer,
        "list": TaskListSerializer,
        "top_logged_tasks_last_month": TopTaskSerializer,
    }
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["title"]
    filterset_fields = ["assignee", "status"]

    def get_queryset(self):
        if self.action == "top_logged_tasks_last_month":
            start, end = get_previous_month_range_utc()
            return (
                Task.objects.filter(
                    Q(time_logs__start_time__gte=start, time_logs__end_time__lte=end)
                    | Q(time_logs__date__gte=start, time_logs__date__lte=end)
                )
                .annotate(total_minutes=Sum("time_logs__duration_minutes"))
                .filter(total_minutes__gt=0, time_logs__user=self.request.user)
                .order_by("-total_minutes")
                .only("id", "title")[:20]
            )
        if self.action == "retrieve":
            return Task.objects.prefetch_related("comments")

        return Task.objects.all()

    @extend_schema(
        request=None,
    )
    @action(detail=True, methods=["patch"])
    def complete(self, request: Request, pk: int) -> Response:
        task: Task = self.get_object()
        serializer: TaskCompleteSerializer = self.get_serializer(
            task, data={"status": Task.Status.COMPLETED}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        task = serializer.save()

        send_to = {comment.author.id for comment in task.comments.all()}
        send_to.add(task.assignee.id)

        task_completed.send(sender=self.__class__, task=task, send_to=send_to)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="assign-user")
    def assign_user(self, request, pk=None):
        task = self.get_object()
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="top-logged-tasks-last-month")
    def top_logged_tasks_last_month(self, request: Request, pk=None):
        cache_key = f"top_logged_tasks_by_user_{request.user.pk}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        top_tasks: QuerySet = self.get_queryset()
        serializer = self.get_serializer(top_tasks, many=True)
        data = serializer.data

        cache.set(cache_key, data, CACHE_TIMEOUTS["TOP_LOGGED_TASKS_BY_USER"])
        return Response(data, status=status.HTTP_200_OK)


class CommentView(MultiSerializerMixin, ListModelMixin, CreateModelMixin, GenericViewSet):
    queryset = Comment.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["task"]
    serializer_class = CommentRetrieveSerializer
    multi_serializer_class = {
        "create": CommentCreateSerializer,
    }


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


class TimeLogView(MultiSerializerMixin, ListModelMixin, DestroyModelMixin, GenericViewSet):
    queryset = TimeLog.objects.all()
    serializer_class = TimeLogSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["task"]
    multi_serializer_class = {
        "start_timer": TimeLogStartSerializer,
        "stop_timer": TimeLogStopSerializer,
        "log_date": TimeLogSpecificDateSerializer,
    }

    @action(detail=False, methods=["post"], url_path="start-timer")
    def start_timer(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TimeLog.objects.filter(start_time__isnull=False, end_time=None).update(
            end_time=serializer.validated_data["start_time"]
        )
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["patch"], url_path="stop-timer")
    def stop_timer(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="log-date")
    def log_date(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttachmentView(MultiSerializerMixin, ListModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Attachment.objects.all()
    serializer_class = AttachmentListSerializer
    multi_serializer_class = {
        "presign_upload": AttachmentPresignUrlSerializer,
        "list": AttachmentListSerializer,
    }

    @action(detail=False, methods=["post"])
    def presign_upload(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            object_name = str(uuid.uuid4())

            attachment = Attachment.objects.create(
                bucket=MINIO_ATTACHMENTS_BUCKET,
                object_name=object_name,
                status=Attachment.Status.PENDING,
                task_id=data["task_id"],
                filename=data["filename"],
            )

            minio_backend = MinioBackend(bucket_name=MINIO_ATTACHMENTS_BUCKET)
            presigned_url = minio_backend.client_external.get_presigned_url(
                method="PUT",
                bucket_name=MINIO_ATTACHMENTS_BUCKET,
                object_name=attachment.object_name,
                expires=MINIO_URL_EXPIRY_HOURS,
            )

        return Response(
            {
                "id": attachment.id,
                "object_name": attachment.object_name,
                "upload_url": presigned_url,
            }
        )


class AttachmentsWebhookView(APIView):
    authentication_classes = [MinioWebhookAuthentication]
    permission_classes = []

    def post(self, request, *args, **kwargs):
        try:
            record = request.data["Records"][0]
            object_key = record["s3"]["object"]["key"]
        except (KeyError, IndexError):
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        updated = Attachment.objects.filter(object_name=object_key).update(status=Attachment.Status.UPLOADED)
        if updated == 0:
            return Response({"error": "Attachment not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": "ok"})
