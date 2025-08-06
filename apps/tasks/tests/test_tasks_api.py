from datetime import timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
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
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="main_user")
        cls.user1 = UserFactory(username="user1")
        cls.user2 = UserFactory(username="user2")

    def setUp(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self._create_test_tasks()

    def _create_test_tasks(self):
        self.task_open_user1 = TaskFactory(status=Task.Status.OPEN, assignee=self.user1)
        self.task_completed_user1 = TaskFactory(status=Task.Status.COMPLETED, assignee=self.user1)
        self.task_open_user2 = TaskFactory(status=Task.Status.OPEN, assignee=self.user2)
        self.task_canceled_user2 = TaskFactory(status=Task.Status.CANCELED, assignee=self.user2)

        self.tasks = [
            self.task_open_user1,
            self.task_completed_user1,
            self.task_open_user2,
            self.task_canceled_user2,
        ]

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
        response = self.client.get(self._get_tasks_list_url())
        expected_data = TaskListSerializer(self.tasks, many=True).data

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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
            ("filter_by_open_status", {"status": Task.Status.OPEN}, "status", Task.Status.OPEN),
            ("filter_by_completed_status", {"status": Task.Status.COMPLETED}, "status", Task.Status.COMPLETED),
        ]
    )
    def test_task_list_filtering(self, name, query_params, filter_field, filter_value):
        expected_tasks = [task for task in self.tasks if getattr(task, filter_field) == filter_value]
        expected_data = TaskListSerializer(expected_tasks, many=True).data

        response = self.client.get(self._get_tasks_list_url(), query_params)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_data)


class TaskRetrieveAPITests(TasksAPITestCase):
    def test_retrieve_existing_task(self):
        task = self.task_open_user1
        expected_data = TaskRetrieveSerializer(task).data

        response = self.client.get(self._get_task_detail_url(task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_data)

    def test_retrieve_nonexistent_task(self):
        response = self.client.get(self._get_task_detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TaskCreateAPITests(TasksAPITestCase):
    @patch("apps.tasks.services.email_service.EmailService.send_task_assigned_notification")
    def test_create_task_success(self, mock_send_task_assigned_notification):
        task_data = {
            "title": "New Task",
            "description": "Task description",
            "status": Task.Status.OPEN,
        }

        response = self.client.post(self._get_tasks_list_url(), data=task_data, format="json")
        created_task = Task.objects.get(id=response.data["id"])
        expected_data = TaskCreateSerializer(created_task).data

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data, expected_data)
        mock_send_task_assigned_notification.assert_called_once_with(created_task)

    def test_create_task_with_invalid_data(self):
        invalid_data = {
            "title": "",
            "status": "INVALID_STATUS",
        }

        response = self.client.post(self._get_tasks_list_url(), data=invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TaskDeleteAPITests(TasksAPITestCase):
    def test_delete_existing_task(self):
        task = self.task_open_user1
        task_id = task.id

        response = self.client.delete(self._get_task_detail_url(task_id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(id=task_id).exists())

    def test_delete_nonexistent_task(self):
        response = self.client.delete(self._get_task_detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TaskCompleteAPITests(TasksAPITestCase):
    def test_complete_open_task(self):
        task = self.task_open_user1

        response = self.client.patch(self._get_task_complete_url(task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)

    def test_complete_already_completed_task(self):
        task = self.task_completed_user1

        response = self.client.patch(self._get_task_complete_url(task.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Task already completed.", response.data["non_field_errors"])

    def test_complete_nonexistent_task(self):
        response = self.client.patch(self._get_task_complete_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TaskAssignAPITests(TasksAPITestCase):
    @patch("apps.tasks.services.email_service.EmailService.send_task_assigned_notification")
    def test_assign_user_to_task(self, mock_send_task_assigned_notification):
        task = self.task_open_user1
        new_assignee = self.user2

        response = self.client.patch(self._get_task_assign_url(task.id), {"assignee": new_assignee.id}, format="json")
        task.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(task.assignee, new_assignee)
        mock_send_task_assigned_notification.assert_called_once_with(task)

    def test_assign_nonexistent_user(self):
        task = self.task_open_user1

        response = self.client.patch(self._get_task_assign_url(task.id), {"assignee": 999999}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_user_to_nonexistent_task(self):
        response = self.client.patch(self._get_task_assign_url(999999), {"assignee": self.user2.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TopTasksAPITests(TasksAPITestCase):
    def test_top_logged_tasks_last_month(self):
        last_month_start = timezone.localtime(timezone.now()).replace(
            day=5, hour=10, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)
        task_data = [
            (self.task_open_user2, 180),
            (self.task_completed_user1, 120),
            (self.task_open_user1, 60),
        ]

        for task, minutes in task_data:
            task.total_minutes = minutes
            task.save()

            if task == self.task_open_user2:
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
            TopTaskSerializer(self.task_open_user2).data,
            TopTaskSerializer(self.task_completed_user1).data,
            TopTaskSerializer(self.task_open_user1).data,
        ]

        for i, expected_task_data in enumerate(expected_order):
            self.assertEqual(response.data[i], expected_task_data)

    def test_top_logged_tasks_empty_result(self):
        response = self.client.get(self._get_top_tasks_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
