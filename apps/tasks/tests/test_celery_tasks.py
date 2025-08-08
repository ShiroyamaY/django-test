from unittest import TestCase
from unittest.mock import patch

from apps.tasks.factories import CommentFactory, TaskFactory
from apps.tasks.services.email_service import EmailService
from apps.tasks.tasks import (
    send_task_assigned_notification,
    send_task_commented_notification,
    send_task_completed_notification,
)
from apps.users.factories import UserFactory


class TestCeleryTasks(TestCase):
    @patch.object(EmailService, "send_mail")
    def test_send_task_assigned_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        task = TaskFactory(assignee__email="assignee@example.com")

        result = send_task_assigned_notification(task.id)

        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_task_assigned_notification_without_email(self):
        task = TaskFactory(assignee__email="")

        result = send_task_assigned_notification(task.id)

        assert result is False

    @patch.object(EmailService, "send_mail")
    def test_send_task_completed_notification(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory(email="1@example.com")
        user2 = UserFactory(email="2@example.com")
        task = TaskFactory()

        result = send_task_completed_notification(task.id, {user1.id, user2.id})

        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_task_completed_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory()
        result = send_task_completed_notification(task.id, {user1.id})

        assert result is False

    @patch.object(EmailService, "send_mail")
    def test_send_task_commented_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory()
        user2 = UserFactory()
        task = TaskFactory(assignee=user2)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        assert result is True

    def test_send_task_commented_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        assert result is False

    def test_send_task_commented_by_assignee(self):
        user1 = UserFactory()
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        assert result is False
