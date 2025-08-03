from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from yaml import serialize

from tms.tasks.models.tasks import Task
from tms.tasks.serializers import TaskSerializer
from tms.tasks.serializers.tasks import TaskCreateSerializer
from tms.tasks.services.email_service import EmailService


class TaskView(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    multi_serializer_class = {
        "create": TaskCreateSerializer,
    }
    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]

    def get_serializer_class(self):
        return self.multi_serializer_class.get(self.action) or self.serializer_class

    def get_queryset(self):
        if self.action in ["comments", "complete"]:
            return Task.objects.prefetch_related("comments")
        return Task.objects.all()

    def perform_create(self, serializer: TaskCreateSerializer):
        task = serializer.save(assignee=self.request.user)
        EmailService.send_task_assigned_notification(task)

    @extend_schema(
        request=None,
    )
    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: int) -> Response:
        task: Task = self.get_object()

        if task.status == Task.Status.COMPLETED:
            return Response(
                "Task already completed.", status=status.HTTP_400_BAD_REQUEST
            )

        task.status = task.Status.COMPLETED
        task.save()

        send_to = {comment.author for comment in task.comments.all()}
        send_to.add(task.assignee)

        EmailService.send_task_completed_notification(task, send_to)

        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)
