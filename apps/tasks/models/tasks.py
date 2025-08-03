from django.contrib.auth.models import User
from django.db import models

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
