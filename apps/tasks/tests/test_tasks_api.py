from datetime import timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.urls.base import reverse
from django.utils import timezone
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tasks.factories import TaskFactory
from apps.tasks.models import Task, TimeLog
from apps.tasks.serializers import TaskCreateSerializer, TaskListSerializer, TaskRetrieveSerializer, TopTaskSerializer
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
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data, expected_data)

    def test_get_empty_tasks_list(self):
        Task.objects.all().delete()

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

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
        self.assertEqual(response.data, expected_data)

    def test_task_list_filtering_no_results(self):
        TaskFactory.create_batch(3, status=Task.Status.OPEN, assignee=self.user1)

        response = self.client.get(self._get_tasks_list_url(), {"status": Task.Status.CANCELED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_task_list_multiple_assignees(self):
        TaskFactory.create_batch(2, assignee=self.user1)
        TaskFactory.create_batch(3, assignee=self.user2)

        response = self.client.get(self._get_tasks_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)


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

    def test_top_logged_tasks_different_users(self):
        last_month_start = timezone.localtime(timezone.now()).replace(
            day=10, hour=14, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)
        task1 = TaskFactory(title="Multi User Task 1", assignee=self.user1)
        task2 = TaskFactory(title="Multi User Task 2", assignee=self.user2)
        TimeLog.objects.create(task=task1, user=self.user1, date=last_month_start.date(), duration_minutes=100)
        TimeLog.objects.create(task=task1, user=self.user2, date=last_month_start.date(), duration_minutes=50)
        TimeLog.objects.create(task=task2, user=self.user1, date=last_month_start.date(), duration_minutes=75)

        response = self.client.get(self._get_top_tasks_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["total_minutes"], 150)
        self.assertEqual(response.data[1]["total_minutes"], 75)

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

        with patch("apps.tasks.views.tasks.TaskView.get_serializer") as mock_get_serializer:
            mock_get_serializer.return_value.data = [{"id": task.id, "title": task.title, "total_minutes": 120}]

            response = self.client.get(self._get_top_tasks_url())

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data[0]["title"], "Cached Task")
            self.assertTrue(cache.get(cache_key))
            mock_get_serializer.assert_called_once()

        with patch("apps.tasks.views.tasks.TaskView.get_serializerвы") as mock_get_serializer:
            response = self.client.get(self._get_top_tasks_url())

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data[0]["title"], "Cached Task")
            mock_get_serializer.assert_not_called()
