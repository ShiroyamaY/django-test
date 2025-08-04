from django.db.models import Sum
from rest_framework import serializers

from apps.tasks.models.tasks import Task
from apps.tasks.serializers.comments import CommentRetrieveSerializer


class TaskRetrieveSerializer(serializers.ModelSerializer):
    comments = CommentRetrieveSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "assignee", "comments")


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("title", "description", "status")


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "assignee")


class TaskAssignUserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "assignee",
        )


class TaskListSerializer(serializers.ModelSerializer):
    total_logged_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ("id", "title", "total_logged_minutes")

    def get_total_logged_minutes(self, obj) -> int:
        return obj.time_logs.aggregate(total=Sum("duration_minutes"))["total"] or 0


class TopTaskSerializer(serializers.ModelSerializer):
    total_minutes = serializers.IntegerField()

    class Meta:
        model = Task
        fields = ["id", "title", "total_minutes"]
