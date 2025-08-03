from django.db import models
from tms.tasks.models.tasks import Task
from django.contrib.auth.models import User


class Comment(models.Model):
    text = models.TextField()
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")

    def __str__(self):
        return self.text
