from django.contrib.auth.models import User
from django.db import models

from apps.tasks.models.tasks import Task


class Comment(models.Model):
    text = models.TextField()
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")

    def __str__(self):
        return self.text
