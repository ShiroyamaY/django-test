import logging
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.urls.base import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tasks.factories import CommentFactory, TaskFactory, TimeLogFactory
from apps.tasks.models import Comment, Task, TimeLog
from apps.tasks.serializers import (
    CommentRetrieveSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskRetrieveSerializer,
    TopTaskSerializer,
)
from apps.tasks.services.email_service import EmailService
from apps.tasks.tasks import (
    send_task_assigned_notification,
    send_task_commented_notification,
    send_task_completed_notification,
    top_tasks_by_logged_time_report,
)
from apps.users.factories import UserFactory


class TasksAPITestCase(APITestCase):
    def setUp(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="main_user")
        cls.user1 = UserFactory(username="user1")
        cls.user2 = UserFactory(username="user2")

    def _get_tasks_list_url(self):
        return reverse("tasks-list")

    def _get_task_detail_url(self, task_id):
        return reverse("tasks-detail", kwargs={"pk": task_id})

    def _get_task_complete_url(self, task_id):
        return reverse("tasks-complete", kwargs={"pk": task_id})

    def _get_task_assign_url(self, task_id):
        return reverse("tasks-assign-user", kwargs={"pk": task_id})

    def _get_top_tasks_url(self):
        return reverse("tasks-top-logged-tasks-last-month")


class TaskListAPITests(TasksAPITestCase):
    def test_get_tasks_list_success(self):
        tasks = [
            TaskFactory(title="Task 1", status=Task.Status.OPEN, assignee=self.user1),
            TaskFactory(title="Task 2", status=Task.Status.COMPLETED, assignee=self.user2),
            TaskFactory(title="Task 3", status=Task.Status.OPEN, assignee=self.user1),
        ]
        expected_data = TaskListSerializer(tasks, many=True).data

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertEqual(response.data["results"], expected_data)

    def test_get_empty_tasks_list(self):
        Task.objects.all().delete()

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_unauthenticated_access_denied(self):
        self.client.credentials()

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @parameterized.expand(
        [
            ("filter_by_open_status", Task.Status.OPEN),
            ("filter_by_completed_status", Task.Status.COMPLETED),
            ("filter_by_canceled_status", Task.Status.CANCELED),
        ]
    )
    def test_task_list_filtering(self, name, filter_status):
        open_task = TaskFactory(status=Task.Status.OPEN, assignee=self.user1)
        completed_task = TaskFactory(status=Task.Status.COMPLETED, assignee=self.user2)
        canceled_task = TaskFactory(status=Task.Status.CANCELED, assignee=self.user1)

        all_tasks = [open_task, completed_task, canceled_task]
        expected_tasks = [task for task in all_tasks if task.status == filter_status]
        expected_data = TaskListSerializer(expected_tasks, many=True).data

        response = self.client.get(self._get_tasks_list_url(), {"status": filter_status})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], expected_data)

    def test_task_list_filtering_no_results(self):
        TaskFactory.create_batch(3, status=Task.Status.OPEN, assignee=self.user1)

        response = self.client.get(self._get_tasks_list_url(), {"status": Task.Status.CANCELED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_task_list_multiple_assignees(self):
        TaskFactory.create_batch(2, assignee=self.user1)
        TaskFactory.create_batch(3, assignee=self.user2)

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)


class TaskRetrieveAPITests(TasksAPITestCase):
    def test_retrieve_existing_task(self):
        task = TaskFactory(
            title="Test Task for Retrieve",
            description="Detailed description",
            status=Task.Status.OPEN,
            assignee=self.user1,
        )
        expected_data = TaskRetrieveSerializer(task).data

        response = self.client.get(self._get_task_detail_url(task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_data)

    def test_retrieve_nonexistent_task(self):
        response = self.client.get(self._get_task_detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_task_different_statuses(self):
        for status_value in [Task.Status.OPEN, Task.Status.COMPLETED, Task.Status.CANCELED]:
            with self.subTest(status=status_value):
                task = TaskFactory(status=status_value, assignee=self.user1)
                expected_data = TaskRetrieveSerializer(task).data

                response = self.client.get(self._get_task_detail_url(task.id))

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data, expected_data)


class TaskCreateAPITests(TasksAPITestCase):
    @patch("apps.tasks.tasks.send_task_assigned_notification.delay")
    def test_create_task_success(self, mock_send_task_assigned_notification_delay):
        task_data = {
            "title": "New Important Task",
            "description": "This is a detailed task description",
            "status": Task.Status.OPEN,
        }

        response = self.client.post(self._get_tasks_list_url(), data=task_data, format="json")
        created_task = Task.objects.get(id=response.data["id"])
        expected_data = TaskCreateSerializer(created_task).data

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data, expected_data)
        self.assertEqual(created_task.title, task_data["title"])
        self.assertEqual(created_task.description, task_data["description"])
        mock_send_task_assigned_notification_delay.assert_called_once_with(created_task.id)

    def test_create_task_with_invalid_data(self):
        invalid_data = {
            "title": "",
            "status": "INVALID_STATUS",
        }

        response = self.client.post(self._get_tasks_list_url(), data=invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_task_missing_required_fields(self):
        incomplete_data = {
            "description": "Task without title",
        }

        response = self.client.post(self._get_tasks_list_url(), data=incomplete_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TaskDeleteAPITests(TasksAPITestCase):
    def test_delete_existing_task(self):
        task = TaskFactory(title="Task to Delete", assignee=self.user1)
        task_id = task.id

        response = self.client.delete(self._get_task_detail_url(task_id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(id=task_id).exists())

    def test_delete_nonexistent_task(self):
        response = self.client.delete(self._get_task_detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_task_different_statuses(self):
        for status_value in [Task.Status.OPEN, Task.Status.COMPLETED, Task.Status.CANCELED]:
            with self.subTest(status=status_value):
                task = TaskFactory(status=status_value, assignee=self.user1)
                task_id = task.id

                response = self.client.delete(self._get_task_detail_url(task_id))

                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
                self.assertFalse(Task.objects.filter(id=task_id).exists())

    def test_delete_task_cascade_effects(self):
        task = TaskFactory(assignee=self.user1)
        task_id = task.id
        TimeLog.objects.create(task=task, user=self.user, date=timezone.now().date(), duration_minutes=60)

        response = self.client.delete(self._get_task_detail_url(task_id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(id=task_id).exists())
        self.assertFalse(TimeLog.objects.filter(task_id=task_id).exists())


class TaskCompleteAPITests(TasksAPITestCase):
    def test_complete_open_task(self):
        task = TaskFactory(title="Task to Complete", status=Task.Status.OPEN, assignee=self.user1)

        response = self.client.patch(self._get_task_complete_url(task.id))
        task.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(task.status, Task.Status.COMPLETED)

    def test_complete_already_completed_task(self):
        task = TaskFactory(status=Task.Status.COMPLETED, assignee=self.user1)

        response = self.client.patch(self._get_task_complete_url(task.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Task already completed.", response.data["non_field_errors"])

    def test_complete_canceled_task(self):
        task = TaskFactory(status=Task.Status.CANCELED, assignee=self.user1)

        response = self.client.patch(self._get_task_complete_url(task.id))

        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

    def test_complete_nonexistent_task(self):
        response = self.client.patch(self._get_task_complete_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_task_updates_timestamp(self):
        task = TaskFactory(status=Task.Status.OPEN, assignee=self.user1)
        original_updated_at = task.updated_at

        response = self.client.patch(self._get_task_complete_url(task.id))
        task.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(task.updated_at, original_updated_at)


class TaskAssignAPITests(TasksAPITestCase):
    @patch("apps.tasks.tasks.send_task_assigned_notification.delay")
    def test_assign_user_to_task(self, mock_send_task_assigned_notification_delay):
        task = TaskFactory(title="Task for Assignment", status=Task.Status.OPEN, assignee=self.user1)
        new_assignee = self.user2

        response = self.client.patch(self._get_task_assign_url(task.id), {"assignee": new_assignee.id}, format="json")

        task.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(task.assignee, new_assignee)
        mock_send_task_assigned_notification_delay.assert_called_once_with(task.id)

    @patch("apps.tasks.tasks.send_task_assigned_notification.delay")
    def test_reassign_task_to_same_user(self, mock_send_task_assigned_notification_delay):
        task = TaskFactory(status=Task.Status.OPEN, assignee=self.user1)

        response = self.client.patch(self._get_task_assign_url(task.id), {"assignee": self.user1.id}, format="json")
        task.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(task.assignee, self.user1)
        mock_send_task_assigned_notification_delay.assert_called_once_with(task.id)

    def test_assign_nonexistent_user(self):
        task = TaskFactory(status=Task.Status.OPEN, assignee=self.user1)

        response = self.client.patch(self._get_task_assign_url(task.id), {"assignee": 999999}, format="json")

        task.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(task.assignee, self.user1)

    def test_assign_user_to_nonexistent_task(self):
        response = self.client.patch(self._get_task_assign_url(999999), {"assignee": self.user2.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TopTasksAPITests(TasksAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_top_logged_tasks_last_month(self):
        last_month_start = timezone.localtime(timezone.now()).replace(
            day=5, hour=10, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)
        high_time_task = TaskFactory(title="High Time Task", assignee=self.user1)
        medium_time_task = TaskFactory(title="Medium Time Task", assignee=self.user2)
        low_time_task = TaskFactory(title="Low Time Task", assignee=self.user1)
        task_data = [
            (high_time_task, 180),
            (medium_time_task, 120),
            (low_time_task, 60),
        ]

        for task, minutes in task_data:
            task.total_minutes = minutes

            if task == high_time_task:
                TimeLog.objects.create(
                    task=task,
                    user=self.user,
                    start_time=last_month_start,
                    end_time=last_month_start + timedelta(hours=3),
                    duration_minutes=minutes,
                )
            else:
                TimeLog.objects.create(
                    task=task, user=self.user, date=last_month_start.date(), duration_minutes=minutes
                )

        response = self.client.get(self._get_top_tasks_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        expected_order = [
            TopTaskSerializer(high_time_task).data,
            TopTaskSerializer(medium_time_task).data,
            TopTaskSerializer(low_time_task).data,
        ]

        for i, expected_task_data in enumerate(expected_order):
            self.assertEqual(response.data[i], expected_task_data)

    def test_top_logged_tasks_empty_result(self):
        Task.objects.all().delete()
        TimeLog.objects.all().delete()

        response = self.client.get(self._get_top_tasks_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_top_logged_tasks_current_month_excluded(self):
        current_month_task = TaskFactory(title="Current Month Task", assignee=self.user1)
        TimeLog.objects.create(
            task=current_month_task, user=self.user, date=timezone.now().date(), duration_minutes=300
        )

        response = self.client.get(self._get_top_tasks_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_top_logged_tasks_limit(self):
        last_month_start = timezone.localtime(timezone.now()).replace(
            day=15, hour=12, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)
        tasks = []
        for i in range(21):
            task = TaskFactory(title=f"Bulk Task {i}", assignee=self.user1)
            total_minutes = (i + 1) * 10
            tasks.append(task)

            TimeLog.objects.create(
                task=task, user=self.user, date=last_month_start.date(), duration_minutes=total_minutes
            )

        response = self.client.get(self._get_top_tasks_url())
        returned_count = len(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(returned_count, 20)
        if returned_count > 1:
            for i in range(returned_count - 1):
                self.assertGreaterEqual(response.data[i]["total_minutes"], response.data[i + 1]["total_minutes"])

    def test_top_logged_tasks_caching(self):
        cache_key = f"top_logged_tasks_by_user_{self.user.pk}"

        task = TaskFactory(title="Cached Task", assignee=self.user)
        TimeLog.objects.create(
            task=task,
            user=self.user,
            duration_minutes=120,
            date=timezone.now().replace(day=1) - relativedelta(months=1),
        )

        with patch("apps.tasks.views.TaskView.get_serializer") as mock_get_serializer:
            mock_get_serializer.return_value.data = [{"id": task.id, "title": task.title, "total_minutes": 120}]

            response = self.client.get(self._get_top_tasks_url())

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data[0]["title"], "Cached Task")
            self.assertTrue(cache.get(cache_key))
            mock_get_serializer.assert_called_once()

        with patch("apps.tasks.views.TaskView.get_serializer") as mock_get_serializer:
            response = self.client.get(self._get_top_tasks_url())

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data[0]["title"], "Cached Task")
            mock_get_serializer.assert_not_called()


class TestCeleryTasks(TestCase):
    @patch.object(EmailService, "send_mail")
    def test_send_task_assigned_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        task = TaskFactory(assignee__email="assignee@example.com")

        result = send_task_assigned_notification(task.id)

        self.assertTrue(result)
        mock_send_mail.assert_called_once()

    def test_send_task_assigned_notification_without_email(self):
        task = TaskFactory(assignee__email="")

        result = send_task_assigned_notification(task.id)

        self.assertFalse(result)

    @patch.object(EmailService, "send_mail")
    def test_send_task_completed_notification(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory(email="1@example.com")
        user2 = UserFactory(email="2@example.com")
        task = TaskFactory()

        result = send_task_completed_notification(task.id, {user1.id, user2.id})

        self.assertTrue(result)
        mock_send_mail.assert_called_once()

    def test_send_task_completed_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory()
        result = send_task_completed_notification(task.id, {user1.id})

        self.assertFalse(result)

    @patch.object(EmailService, "send_mail")
    def test_send_task_commented_notification_success(self, mock_send_mail):
        mock_send_mail.return_value = True
        user1 = UserFactory()
        user2 = UserFactory()
        task = TaskFactory(assignee=user2)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        self.assertTrue(result)

    def test_send_task_commented_notification_with_no_emails(self):
        user1 = UserFactory(email="")
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        self.assertFalse(result)

    def test_send_task_commented_by_assignee(self):
        user1 = UserFactory()
        task = TaskFactory(assignee=user1)
        comment = CommentFactory(task=task, author=user1)

        result = send_task_commented_notification(comment.id)

        self.assertFalse(result)

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

                self.assertTrue(result)
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

            self.assertFalse(result)
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

                self.assertFalse(result)
                mock_logger.error.assert_called_once()
                assert "Exception" in mock_logger.error.call_args[0][0]


class TestCommentsAPI(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self._authenticate_user(self.user)

        self.task = TaskFactory(
            status=Task.Status.OPEN,
            assignee=self.user,
        )

    def _authenticate_user(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _get_task_comments_list_url(self, task_id=None):
        if task_id:
            return reverse("tasks-comments-list") + f"?task={task_id}"
        return reverse("tasks-comments-list")

    def test_create_comment_success(self):
        data = {
            "text": "This is a test comment",
            "task": self.task.id,
        }

        response = self.client.post(self._get_task_comments_list_url(), data, format="json")
        comment = Comment.objects.filter(task=self.task.id).first()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(comment)
        self.assertEqual(comment.text, data["text"])
        self.assertEqual(comment.task.id, data["task"])
        self.assertEqual(comment.author, self.user)

        self.assertEqual(response.data["text"], data["text"])
        self.assertEqual(response.data["task"], data["task"])

    @parameterized.expand(
        [
            ("empty_text", {"text": "", "task": 1}, "Empty text should not be allowed"),
            ("missing_task", {"text": "Valid text"}, "Task field is required"),
            ("nonexistent_task", {"text": "Valid text", "task": 99999}, "Task does not exist"),
            ("none_text", {"text": None, "task": 1}, "Text cannot be None"),
            ("whitespace_only_text", {"text": "   ", "task": 1}, "Whitespace-only text should not be allowed"),
        ]
    )
    def test_create_comment_validation_errors(self, name, data, description):
        if "task" in data and data["task"] == 1:
            data["task"] = self.task.id

        response = self.client.post(self._get_task_comments_list_url(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, description)

    def test_create_comment_unauthorized(self):
        data = {
            "text": "Unauthorized comment",
            "task": self.task.id,
        }
        self.client.credentials()

        response = self.client.post(self._get_task_comments_list_url(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_comments_success(self):
        comments = [CommentFactory(task=self.task, author=self.user) for i in range(3)]

        expected_data = CommentRetrieveSerializer(comments, many=True).data
        response = self.client.get(self._get_task_comments_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], expected_data)

    def test_list_comments_filtered_by_task(self):
        for _i in range(4):
            CommentFactory(task=self.task, author=self.user)

        response = self.client.get(self._get_task_comments_list_url(self.task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for comment_data in response.data["results"]:
            self.assertEqual(comment_data["task"], self.task.id)

    def test_list_comments_empty_result(self):
        response = self.client.get(self._get_task_comments_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_list_comments_unauthorized(self):
        self.client.credentials()

        response = self.client.get(self._get_task_comments_list_url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_author_auto_assignment(self):
        data = {
            "text": "Test comment",
            "task": self.task.id,
        }

        response = self.client.post(self._get_task_comments_list_url(), data, format="json")
        comment = Comment.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(comment.author, self.user)


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

    @patch("apps.tasks.services.email_service.EmailMultiAlternatives.send", side_effect=ConnectionError("error"))
    def test_send_email_template_connection_error(self, mock_email_multi_alternatives_send):
        success = EmailService.send_mail("subj", "hm.html", ["user@example.com"])

        assert success is False


class SearchViewTests(APITestCase):
    url = reverse("search")

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="main_user")

    def setUp(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch("apps.tasks.documents.TaskDocument.search")
    def test_search_task_success(self, mock_task_search):
        mock_search_instance = MagicMock()
        mock_task_search.return_value = mock_search_instance
        mock_search_instance.query.return_value = mock_search_instance
        mock_search_instance.execute.return_value = [
            MagicMock(to_dict=lambda: {"title": "Task1", "description": "Desc1"}, meta=MagicMock(id="1")),
        ]

        response = self.client.get(self.url, {"target": "task", "query": "Desc1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Task1")
        mock_task_search.assert_called_once()
        mock_search_instance.query.assert_called_once_with(
            "multi_match", query="Desc1", fields=["title", "description"]
        )
        mock_search_instance.execute.assert_called_once()

    @patch("apps.tasks.documents.CommentDocument.search")
    def test_search_comment_success(self, mock_comment_search):
        mock_search_instance = MagicMock()
        mock_comment_search.return_value = mock_search_instance
        mock_search_instance.query.return_value = mock_search_instance
        mock_search_instance.execute.return_value = [
            MagicMock(to_dict=lambda: {"text": "Comment text"}, meta=MagicMock(id="2")),
        ]

        response = self.client.get(self.url, {"target": "comment", "query": "Comment text"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["text"], "Comment text")
        mock_comment_search.assert_called_once()
        mock_search_instance.query.assert_called_once_with("match", text="Comment text")
        mock_search_instance.execute.assert_called_once()

    def test_search_invalid_target(self):
        response = self.client.get(self.url, {"target": "invalid", "query": "test"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not a valid choice", str(response.data["target"]))

    def test_search_missing_params(self):
        response = self.client.get(self.url, {"target": "task"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(self.url, {"query": "test"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestTimeLogsAPI(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self._authenticate_user(self.user)

        self.task_open = TaskFactory(
            status=Task.Status.OPEN,
            assignee=self.user,
        )

        self.task_completed = TaskFactory(
            status=Task.Status.COMPLETED,
            assignee=self.user,
        )

    def _authenticate_user(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _get_task_time_logs_log_date_url(self):
        return reverse("tasks-time-logs-log-date")

    def _get_task_time_logs_start_timer_url(self):
        return reverse("tasks-time-logs-start-timer")

    def _get_task_time_logs_stop_timer_url(self):
        return reverse("tasks-time-logs-stop-timer")

    def test_time_logs_log_date_success(self):
        data = {
            "task": self.task_open.id,
            "date": datetime.now().date().strftime("%Y-%m-%d"),
            "duration_minutes": 60,
        }

        response = self.client.post(self._get_task_time_logs_log_date_url(), data, format="json")
        self.assertEqual(response.data, data)

    def test_time_logs_start_timer_success(self):
        now = make_aware(datetime.now())
        data = {
            "task": self.task_open.id,
            "start_time": now,
        }

        response = self.client.post(self._get_task_time_logs_start_timer_url(), data, format="json")
        response_time = parse_datetime(response.data["start_time"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["task"], data["task"])
        self.assertAlmostEqual(response_time, now)
        self.assertIn("id", response.data)

    def test_time_logs_stop_timer_success(self):
        start_time = make_aware(datetime.now())
        end_time = start_time + relativedelta(hours=1)
        data = {
            "task": self.task_open.id,
            "end_time": end_time,
        }
        TimeLogFactory(task=self.task_open, user=self.user, start_time=start_time, end_time=None, duration_minutes=None)

        response = self.client.patch(self._get_task_time_logs_stop_timer_url(), data, format="json")

        self.assertEqual(response.data["task"], data["task"])
        self.assertEqual(response.data["duration_minutes"], 60)

    def test_time_logs_stop_timer_returns_no_active_timer(self):
        end_time = make_aware(datetime.now())
        data = {
            "task": self.task_open.id,
            "end_time": end_time,
        }

        response = self.client.patch(self._get_task_time_logs_stop_timer_url(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"][0], "Active timer not found for this task.")

    def test_time_logs_stop_timer_returns_no_invalid_duration_error(self):
        now = make_aware(datetime.now())
        data = {
            "task": self.task_open.id,
            "end_time": now,
        }
        TimeLogFactory(task=self.task_open, user=self.user, start_time=now, end_time=None, duration_minutes=None)

        response = self.client.patch(self._get_task_time_logs_stop_timer_url(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["non_field_errors"][0], "Timelog duration must be greater than zero.")

    def test_time_logs_start_timer_stops_active_timer(self):
        now = make_aware(datetime.now())
        active_timelog = TimeLogFactory(
            task=self.task_open, user=self.user, start_time=now, end_time=None, duration_minutes=None
        )
        data = {
            "task": self.task_open.id,
            "start_time": now + relativedelta(hours=3),
        }

        self.client.post(self._get_task_time_logs_start_timer_url(), data, format="json")

        active_timelog.refresh_from_db()
        self.assertEqual(active_timelog.end_time, data["start_time"])

    def test_time_logs_log_date_unauthorized(self):
        self.client.credentials()

        response = self.client.post(self._get_task_time_logs_log_date_url(), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_time_logs_start_timer_unauthorized(self):
        self.client.credentials()

        response = self.client.post(self._get_task_time_logs_start_timer_url(), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_time_logs_stop_timer_unauthorized(self):
        self.client.credentials()

        response = self.client.post(self._get_task_time_logs_stop_timer_url(), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
