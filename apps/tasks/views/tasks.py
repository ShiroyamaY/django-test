from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.views import MultiSerializerMixin
from apps.tasks.models.tasks import Task
from apps.tasks.serializers.tasks import (
    TaskAssignUserSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskRetrieveSerializer,
    TaskUpdateSerializer,
    TopTaskSerializer,
)
from apps.tasks.services.email_service import EmailService
from apps.tasks.services.task_service import TaskService


class TaskView(MultiSerializerMixin, ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskRetrieveSerializer
    permission_classes = [IsAuthenticated]
    multi_serializer_class = {
        "create": TaskCreateSerializer,
        "assign_user": TaskAssignUserSerializer,
        "update": TaskUpdateSerializer,
        "complete": TaskUpdateSerializer,
        "list": TaskListSerializer,
        "top_logged_tasks_last_month": TopTaskSerializer,
    }
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["title"]
    filterset_fields = ["assignee", "status"]

    def get_queryset(self):
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

        if task.status == Task.Status.COMPLETED:
            return Response("Task already completed.", status=status.HTTP_400_BAD_REQUEST)
        task.status = task.Status.COMPLETED
        task.save()

        send_to = {comment.author for comment in task.comments.all()}
        send_to.add(task.assignee)
        EmailService.send_task_completed_notification(task, send_to)

        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="assign-user")
    def assign_user(self, request, pk=None):
        task = self.get_object()
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        EmailService.send_task_assigned_notification(task)

        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="top-logged-tasks-last-month")
    def top_logged_tasks_last_month(self, request: Request, pk=None):
        top_tasks: QuerySet = TaskService.get_top_logged_tasks_last_month(20)

        return Response(self.get_serializer(top_tasks, many=True).data, status=status.HTTP_200_OK)
