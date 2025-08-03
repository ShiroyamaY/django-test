from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tasks.views.comments import CommentView
from apps.tasks.views.tasks import TaskView

router = DefaultRouter()


router.register("comments", CommentView, basename="comments")
router.register("", TaskView, basename="tasks")
urlpatterns = [
    path("", include(router.urls)),
]
