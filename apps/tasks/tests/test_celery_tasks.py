from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.tasks.factories import CommentFactory, TaskFactory
from apps.tasks.services.email_service import EmailService
from apps.tasks.tasks import (
    send_task_assigned_notification,
    send_task_commented_notification,
    send_task_completed_notification,
    top_tasks_by_logged_time_report,
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

    @patch("apps.tasks.tasks.logger")
    @patch.object(EmailService, "send_mail")
    def test_report_success(self, mock_send_mail, mock_logger):
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")

        TaskFactory.create_batch(2)

        with patch("apps.tasks.tasks.Task.objects.annotate") as mock_annotate:
            mock_qs = MagicMock()
            top_tasks = [
                {"id": 1, "title": "Task 1", "total_minutes": 120},
                {"id": 2, "title": "Task 2", "total_minutes": 90},
            ]
            mock_qs.filter.return_value.order_by.return_value.values.return_value = top_tasks
            mock_annotate.return_value = mock_qs

            with patch("apps.tasks.tasks.User.objects.values_list") as mock_users:
                mock_users.return_value = [user1.email, user2.email]

                mock_send_mail.return_value = True

                result = top_tasks_by_logged_time_report()

                assert result is True
                mock_send_mail.assert_called_once_with(
                    "Top tasks by logged time",
                    "emails/top_tasks_by_logged_time.html",
                    [user1.email, user2.email],
                    {"tasks": top_tasks},
                )
                mock_logger.error.assert_not_called()

    @patch("apps.tasks.tasks.logger")
    @patch.object(EmailService, "send_mail")
    def test_report_no_tasks(self, mock_send_mail, mock_logger):
        TaskFactory.create_batch(1)

        with patch("apps.tasks.tasks.Task.objects.annotate") as mock_annotate:
            mock_qs = MagicMock()
            mock_qs.filter.return_value.order_by.return_value.values.return_value = []
            mock_annotate.return_value = mock_qs

            result = top_tasks_by_logged_time_report()

            assert result is False
            mock_send_mail.assert_not_called()
            mock_logger.error.assert_called_once()
            assert "Validation error" in mock_logger.error.call_args[0][0]

    @patch("apps.tasks.tasks.logger")
    @patch.object(EmailService, "send_mail")
    def test_report_send_mail_exception(self, mock_send_mail, mock_logger):
        TaskFactory.create_batch(1)

        with patch("apps.tasks.tasks.Task.objects.annotate") as mock_annotate:
            mock_qs = MagicMock()
            top_tasks = [{"id": 1, "title": "Task 1", "total_minutes": 120}]
            mock_qs.filter.return_value.order_by.return_value.values.return_value = top_tasks
            mock_annotate.return_value = mock_qs

            with patch("apps.tasks.tasks.User.objects.values_list") as mock_users:
                user = UserFactory(email="user@example.com")
                mock_users.return_value = [user.email]

                mock_send_mail.side_effect = Exception("Email sending failed")

                result = top_tasks_by_logged_time_report()

                assert result is False
                mock_logger.error.assert_called_once()
                assert "Exception" in mock_logger.error.call_args[0][0]
