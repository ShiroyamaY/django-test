from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tasks.views.attachments import AttachmentView
from apps.tasks.views.comments import CommentView
from apps.tasks.views.search import SearchView
from apps.tasks.views.tasks import TaskView
from apps.tasks.views.time_logs import TimeLogView

router = DefaultRouter()

router.register("tasks/attachments", AttachmentView, basename="tasks-attachments")
router.register("tasks/comments", CommentView, basename="tasks-comments")
router.register("tasks/time-logs", TimeLogView, basename="tasks-time-logs")
router.register("tasks", TaskView, basename="tasks")

urlpatterns = [
    path("", include(router.urls)),
    path("search", SearchView.as_view(), name="search"),
]
