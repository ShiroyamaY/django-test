import logging
from unittest.mock import patch

from django.core.mail.message import EmailMultiAlternatives
from django.template.exceptions import TemplateDoesNotExist, TemplateSyntaxError
from rest_framework.test import APITestCase

from apps.tasks.factories import CommentFactory, TaskFactory
from apps.tasks.services.email_service import EmailService
from apps.users.factories import UserFactory


class TestEmailService(APITestCase):
    def setUp(self):
        logging.disable(logging.ERROR)

    @patch("apps.tasks.services.email_service.render_to_string")
    @patch.object(EmailMultiAlternatives, "send")
    def test_send_email_success(self, mock_email_multi_alternatives_send, mock_render_to_string):
        mock_render_to_string.return_value = "<html><body>Hello, world!</body></html>"
        mock_email_multi_alternatives_send.return_value = None

        success = EmailService.send_mail(
            subject="Hello, world!",
            template="emails/test.html",
            to=["pavel.termhg.com"],
            context={"foo": "bar"},
        )

        assert success is True
        mock_email_multi_alternatives_send.assert_called_once()

    @patch("apps.tasks.services.email_service.render_to_string", side_effect=TemplateDoesNotExist("error"))
    def test_send_email_template_not_found(self, mock_email_service_render_to_string):
        success = EmailService.send_mail("subj", "invalid.html", ["user@example.com"])
        assert success is False

    @patch("apps.tasks.services.email_service.render_to_string", side_effect=TemplateSyntaxError("error"))
    def test_send_email_template_syntax_error(self, mock_email_service_render_to_string):
        success = EmailService.send_mail("subj", "broken.html", ["user@example.com"])
        assert success is False

    @patch.object(EmailMultiAlternatives, "send", side_effect=ConnectionError("error"))
    def test_send_email_template_connection_error(self, mock_email_multi_alternatives_send):
        success = EmailService.send_mail("subj", "hm.html", ["user@example.com"])

        assert success is False

    @patch.object(EmailService, "send_mail")
    def test_send_task_assigned_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        task = TaskFactory(assignee__email="assignee@example.com")

        result = EmailService.send_task_assigned_notification(task)

        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_task_assigned_notification_without_email(self):
        task = TaskFactory(assignee__email="")

        result = EmailService.send_task_assigned_notification(task)

        assert result is False

    @patch.object(EmailService, "send_mail")
    def test_send_task_completed_notification(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory(email="1@example.com")
        user2 = UserFactory(email="2@example.com")
        task = TaskFactory()

        result = EmailService.send_task_completed_notification(task, {user1, user2})

        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_task_completed_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory()
        result = EmailService.send_task_completed_notification(task, {user1})

        assert result is False

    @patch.object(EmailService, "send_mail")
    def test_send_task_commented_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory()
        user2 = UserFactory()
        task = TaskFactory(assignee=user2)
        comment = CommentFactory(task=task, author=user1)

        result = EmailService.send_task_commented_notification(comment)

        assert result is True

    def test_send_task_commented_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = EmailService.send_task_commented_notification(comment)

        assert result is False

    def test_send_task_commented_by_assignee(self):
        user1 = UserFactory()
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = EmailService.send_task_commented_notification(comment)

        assert result is False
