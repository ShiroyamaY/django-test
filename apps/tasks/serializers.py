from django.db.models.aggregates import Sum
from rest_framework import serializers

from apps.tasks.models import Comment, Task, TimeLog


class CommentRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("text", "task", "author")


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = (
            "text",
            "task",
        )


class TaskRetrieveSerializer(serializers.ModelSerializer):
    comments = CommentRetrieveSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "assignee", "comments")


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status")


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "assignee")


class TaskCompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "status")

    def validate(self, attrs):
        if self.instance.status == Task.Status.COMPLETED:
            raise serializers.ValidationError("Task already completed.")
        return attrs


class TaskAssignUserSerializer(serializers.ModelSerializer):
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
    total_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = ["id", "title", "total_minutes"]


class TimeLogStartSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault(), write_only=True)

    class Meta:
        model = TimeLog
        fields = (
            "id",
            "task",
            "start_time",
            "user",
        )


class TimeLogStopSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.SerializerMethodField()
    end_time = serializers.DateTimeField(write_only=True)

    class Meta:
        model = TimeLog
        fields = ("id", "task", "end_time", "duration_minutes")

    def get_duration_minutes(self, obj) -> int:
        return obj["time_log"].calculate_duration()

    def validate(self, attrs):
        user = self.context["request"].user
        task = attrs["task"]
        end_time = attrs["end_time"]

        time_log = TimeLog.objects.filter(task=task, user=user, end_time__isnull=True).first()
        if not time_log:
            raise serializers.ValidationError("Active timer not found for this task.")

        duration = (end_time - time_log.start_time).total_seconds() / 60
        if duration <= 0:
            raise serializers.ValidationError("Timelog duration must be greater than zero.")

        attrs["time_log"] = time_log
        return attrs

    def save(self, **kwargs):
        time_log = self.validated_data["time_log"]

        time_log.end_time = self.validated_data["end_time"]
        time_log.duration_minutes = time_log.calculate_duration()
        time_log.save()

        return time_log


class TimeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeLog
        fields = "__all__"


class TimeLogSpecificDateSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(min_value=1)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault(), write_only=True)

    class Meta:
        model = TimeLog
        fields = ("task", "date", "duration_minutes", "user")
