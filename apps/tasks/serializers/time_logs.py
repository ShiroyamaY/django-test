from rest_framework import serializers

from apps.tasks.models.time_logs import TimeLog


class TimeLogStartSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = TimeLog
        fields = (
            "id",
            "task",
            "start_time",
        )

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user

        TimeLog.objects.filter(end_time=None).update(end_time=validated_data["start_time"])

        return super().create(validated_data)


class TimeLogStopSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
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

    class Meta:
        model = TimeLog
        fields = (
            "task",
            "date",
            "duration_minutes",
        )

    def create(self, validated_data: dict):
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)
