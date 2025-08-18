import logging
from typing import Any

from celery import shared_task
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.db.models.aggregates import Sum

from apps.tasks.models import Comment, Task
from apps.tasks.services import EmailService

logger = logging.getLogger("apps.tasks")


@shared_task
def send_task_assigned_notification(task_id: int):
    try:
        task = Task.objects.filter(id=task_id).first()
        if not task:
            raise ValueError("Task not found")

        if not task.assignee or not task.assignee.email:
            raise ValueError("Assignee does not have an email address.")

        subject = f"You have been assigned a task: {task.title}"

        context = {
            "task": task,
            "user": task.assignee,
        }

        return EmailService.send_mail(subject, "emails/task_assigned.html", [task.assignee.email], context)
    except ValueError as error:
        logger.error(f"send_task_assigned_notification: Validation error: {error}")
        return False


@shared_task
def send_task_completed_notification(task_id: int, recipients_ids: set[int]):
    try:
        recipients = User.objects.filter(id__in=recipients_ids).all()
        task = Task.objects.filter(id=task_id).first()

        if not task:
            raise ValueError("Task not found")

        if not recipients:
            raise ValueError("Recipients not found")

        emails = [user.email for user in recipients if user.email and user.email.strip()]
        if not emails:
            raise ValueError("No valid emails in recipients list.")

        subject = f"Task completed: {task.title}"
        context = {
            "task": task,
        }

        return EmailService.send_mail(subject, "emails/task_completed.html", emails, context)
    except ValueError as error:
        logger.error(f"send_task_completed_notification: Validation error: {error}")
        return False


@shared_task
def send_task_commented_notification(comment_id: int):
    try:
        comment = Comment.objects.filter(id=comment_id).first()

        if not comment:
            raise ValueError("Comment does not exist.")

        task: Task = comment.task
        author: User = comment.author

        if not task.assignee or not task.assignee.email:
            raise ValueError("Assignee does not have an email address.")

        if task.assignee == author:
            return False

        subject = f"New comment on your task: {task.title}"

        context = {
            "task": task,
            "user": task.assignee,
            "author": author,
            "comment": comment,
        }

        return EmailService.send_mail(subject, "emails/task_commented.html", [task.assignee.email], context)
    except ValueError as error:
        logger.error(f"send_task_commented_notification: Validation error: {error}")
        return False


@shared_task
def top_tasks_by_logged_time_report():
    try:
        top_tasks: QuerySet[Task, dict[str, Any]] = (
            Task.objects.annotate(total_minutes=Sum("time_logs__duration_minutes"))
            .filter(total_minutes__gt=0)
            .order_by("-total_minutes")
            .values("id", "title", "total_minutes")[:20]
        )

        if not top_tasks:
            raise ValueError("No tasks with logged time in last month.")

        subject = "Top tasks by logged time"
        users_ids = User.objects.values_list("email", flat=True)

        return EmailService.send_mail(subject, "emails/top_tasks_by_logged_time.html", users_ids, {"tasks": top_tasks})
    except ValueError as error:
        logger.error(f"top_tasks_by_logged_time_report: Validation error: {error}")
        return False
    except Exception as error:
        logger.error(f"top_tasks_by_logged_time_report: Exception: {error}")
        return False
