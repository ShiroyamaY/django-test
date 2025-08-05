from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tasks.factories import TaskFactory, TimeLogFactory
from apps.users.factories import UserFactory
from apps.users.serializers import UserListSerializer


class UsersAPITestCase(APITestCase):
    def setUp(self):
        self.users = UserFactory.create_batch(2)

    def set_credentials(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @staticmethod
    def _get_users_list_url():
        return reverse("users-list")

    @staticmethod
    def _get_users_logged_time_last_month_url():
        return reverse("users-logged-time-last-month")

    @staticmethod
    def _get_users_register_url():
        return reverse("users-register")

    def test_users_list_success(self):
        serializer = UserListSerializer(self.users, many=True)

        self.set_credentials(self.users[0])
        response = self.client.get(self._get_users_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_users_list_unauthorized(self):
        response = self.client.get(self._get_users_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_users_list_logged_time_last_month_returns_correct_duration(self):
        user = self.users[0]
        task = TaskFactory(assignee=user)

        last_month_day = timezone.localtime(timezone.now()).replace(
            day=5, hour=10, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)

        time_logs = [
            TimeLogFactory(task=task, user=user, date=last_month_day, duration_minutes=520),
            TimeLogFactory(
                task=task,
                user=user,
                start_time=last_month_day,
                end_time=last_month_day + relativedelta(hours=3),
                duration_minutes=180,
            ),
        ]

        total_minutes = sum(log.duration_minutes for log in time_logs)

        self.set_credentials(user)
        response = self.client.get(self._get_users_logged_time_last_month_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_minutes"], total_minutes)

    def test_users_list_logged_time_last_month_unauthorized(self):
        response = self.client.get(self._get_users_logged_time_last_month_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_user_success(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "strong_password_123",
        }

        response = self.client.post(self._get_users_register_url(), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("user", response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "new@example.com")

    def test_register_user_invalid_data(self):
        data = {
            "username": "baduser",
            "email": "bad@example.com",
        }

        response = self.client.post(self._get_users_register_url(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_user_email_already_in_use(self):
        repeated_email = "exist@example.com"
        data = {
            "username": "user",
            "email": repeated_email,
            "password": "password43534534534534sfs",
        }
        UserFactory(email=repeated_email)

        response = self.client.post(self._get_users_register_url(), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"][0], "This email is already in use.")

    def test_register_user_username_already_taken(self):
        repeated_username = "user"
        UserFactory(username=repeated_username)
        data = {
            "username": repeated_username,
            "email": "some@email.com",
            "password": "password43534534534534sfs",
        }

        response = self.client.post(self._get_users_register_url(), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["username"][0], "This username is already taken.")
