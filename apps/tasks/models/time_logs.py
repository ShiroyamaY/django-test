from datetime import datetime

from django.contrib.auth.models import User
from django.db import models

from apps.common.models import TimeStampMixin
from apps.tasks.models.tasks import Task


class TimeLog(TimeStampMixin, models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_logs")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_logs")

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    date = models.DateField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_duration(self):
        if self.start_time and self.end_time:
            if isinstance(self.start_time, str):
                self.start_time = datetime.fromisoformat(self.start_time)
            if isinstance(self.end_time, str):
                self.end_time = datetime.fromisoformat(self.end_time)

            delta = self.end_time - self.start_time
            return int(delta.total_seconds() // 60)
        return self.duration_minutes
