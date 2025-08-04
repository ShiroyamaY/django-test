import logging
from smtplib import SMTPException

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.tasks.models.comments import Comment
from apps.tasks.models.tasks import Task
from config import settings

logger = logging.getLogger("apps.tasks")


class EmailService:
    @classmethod
    def send_mail(cls, subject: str, template: str, to: list[str], context=None):
        try:
            html_content = render_to_string(template, context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to,
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            return True

        except TemplateDoesNotExist as error:
            logger.error(f"Email Service: Email template not found: {error}")
            return False
        except TemplateSyntaxError as error:
            logger.error(f"Email Service: Template syntax error: {error}")
            return False
        except SMTPException as error:
            logger.error(f"Email Service: SMTP error occurred: {error}")
            return False
        except ConnectionRefusedError as error:
            logger.error(f"Email Service: Connection refused error: {error}")
            return False

    @classmethod
    def send_task_assigned_notification(cls, task: Task):
        try:
            if not task.assignee or not task.assignee.email:
                raise ValueError("Assignee does not have an email address.")

            subject = f"You have been assigned a task: {task.title}"

            context = {
                "task": task,
                "user": task.assignee,
            }

            return cls.send_mail(subject, "emails/task_assigned.html", [task.assignee.email], context)
        except ValueError as error:
            logger.error(f"Email Service: Validation error: {error}")
            return False

    @classmethod
    def send_task_completed_notification(cls, task: Task, recipients: set[User]):
        try:
            emails = [user.email for user in recipients]
            if not emails:
                raise ValueError("No valid emails in recipients list.")

            subject = f"Task completed: {task.title}"
            context = {
                "task": task,
            }

            return cls.send_mail(subject, "emails/task_completed.html", emails, context)
        except ValueError as error:
            logger.error(f"Email Service: Validation error: {error}")
            return False

    @classmethod
    def send_task_commented_notification(cls, comment: Comment):
        try:
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

            return cls.send_mail(subject, "emails/task_commented.html", [task.assignee.email], context)
        except ValueError as error:
            logger.error(f"Email Service: Validation error: {error}")
            return False
