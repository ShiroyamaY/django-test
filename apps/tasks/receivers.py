from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tasks.models import Comment, Task
from apps.tasks.signals import task_completed
from apps.tasks.tasks import (
    send_task_assigned_notification,
    send_task_commented_notification,
    send_task_completed_notification,
)


@receiver(post_save, sender=Task)
def create_or_update_task_document(sender: str, instance: Task, created: bool, **kwargs):
    send_task_assigned_notification.delay(instance.id)


@receiver(post_save, sender=Comment)
def create_or_update_comment_document(sender: str, instance: Comment, created: bool, **kwargs):
    if created:
        send_task_commented_notification.delay(instance.id)


@receiver(task_completed)
def handle_task_completed(sender, **kwargs):
    task = kwargs.get("task")
    user_ids = kwargs.get("send_to", [])
    if task and user_ids:
        send_task_completed_notification.delay(task.id, list(user_ids))
