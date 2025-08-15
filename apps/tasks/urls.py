from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tasks.views import AttachmentsWebhookView, AttachmentView, CommentView, SearchView, TaskView, TimeLogView

router = DefaultRouter()

router.register("tasks/attachments", AttachmentView, basename="tasks-attachments")
router.register("tasks/comments", CommentView, basename="tasks-comments")
router.register("tasks/time-logs", TimeLogView, basename="tasks-time-logs")
router.register("tasks", TaskView, basename="tasks")

urlpatterns = [
    path("", include(router.urls)),
    path("search", SearchView.as_view(), name="search"),
    path("webhooks/minio/attachments", AttachmentsWebhookView.as_view(), name="webhook-minio-attachments"),
]
