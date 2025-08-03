from rest_framework import serializers

from .comments import CommentRetrieveSerializer
from tms.tasks.models.tasks import Task


class TaskSerializer(serializers.ModelSerializer):
    comments = CommentRetrieveSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "assignee", "comments")


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("title", "description", "status")
