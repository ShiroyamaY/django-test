from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from tms.tasks.models.comments import Comment
from tms.tasks.serializers.comments import (
    CommentCreateSerializer,
    CommentRetrieveSerializer,
)
from tms.tasks.services.email_service import EmailService


class CommentView(ListModelMixin, CreateModelMixin, GenericViewSet):
    queryset = Comment.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["task"]
    serializer_class = CommentRetrieveSerializer
    multi_serializer_class = {
        "create": CommentCreateSerializer,
    }

    def get_serializer_class(self):
        return self.multi_serializer_class.get(self.action) or self.serializer_class

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        EmailService.send_task_commented_notification(comment)
