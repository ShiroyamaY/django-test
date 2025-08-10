from django.urls.base import reverse
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tasks.factories import CommentFactory, TaskFactory
from apps.tasks.models import Comment, Task
from apps.tasks.serializers import CommentRetrieveSerializer
from apps.users.factories import UserFactory


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
