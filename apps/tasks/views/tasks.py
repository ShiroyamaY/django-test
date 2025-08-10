from django.core.cache import cache
from django.db.models import QuerySet
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.helpers import get_previous_month_range_utc
from apps.common.views import MultiSerializerMixin
from apps.tasks.models import Task
from apps.tasks.serializers import (
    TaskAssignUserSerializer,
    TaskCompleteSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskRetrieveSerializer,
    TaskUpdateSerializer,
    TopTaskSerializer,
)
from apps.tasks.services.email_service import EmailService
from config.settings import CACHE_TIMEOUTS


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
                .filter(total_minutes__gt=0)
                .order_by("-total_minutes")
                .only("id", "title")[:20]
            )
        if self.action == "retrieve":
            return Task.objects.prefetch_related("comments")

        return Task.objects.all()

    def perform_create(self, serializer: TaskCreateSerializer):
        task = serializer.save(assignee=self.request.user)
        EmailService.send_task_assigned_notification(task)

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

        send_to = {comment.author for comment in task.comments.all()}
        send_to.add(task.assignee)

        EmailService.send_task_completed_notification(task, send_to)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="assign-user")
    def assign_user(self, request, pk=None):
        task = self.get_object()
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()

        EmailService.send_task_assigned_notification(task)

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
