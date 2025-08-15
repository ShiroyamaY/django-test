from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db.models import TextChoices

from apps.common.models import TimeStampMixin


class Task(TimeStampMixin, models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")

    class Status(models.TextChoices):
        OPEN = "Open"
        IN_PROGRESS = "In Progress"
        COMPLETED = "Completed"
        CANCELED = "Canceled"
        ARCHIVED = "Archived"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    def __str__(self):
        return self.title


class Comment(TimeStampMixin, models.Model):
    text = models.TextField()
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")

    def __str__(self):
        return self.text


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


class Attachment(TimeStampMixin, models.Model):
    class Status(TextChoices):
        PENDING = "Pending"
        UPLOADED = "Uploaded"
        FAILED = "Failed"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=20)
    bucket = models.CharField(max_length=255, blank=True, null=True)
    content_type = models.CharField(max_length=255, blank=True, null=True)
    object_name = models.CharField(max_length=255)
