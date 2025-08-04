from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tasks.views.comments import CommentView
from apps.tasks.views.tasks import TaskView
from apps.tasks.views.time_logs import TimeLogView

router = DefaultRouter()


router.register("comments", CommentView, basename="comments")
router.register("time-logs", TimeLogView, basename="time_logs")
router.register("tasks", TaskView, basename="tasks")
urlpatterns = [
    path("", include(router.urls)),
]
