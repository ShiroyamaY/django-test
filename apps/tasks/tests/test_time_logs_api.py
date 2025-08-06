from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.urls.base import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tasks.factories import TaskFactory, TimeLogFactory
from apps.tasks.models import Task
from apps.users.factories import UserFactory


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
