from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.factories import UserFactory


class SearchViewTests(APITestCase):
    url = reverse("search")

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="main_user")

    def setUp(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch("apps.tasks.elasticsearch_documents.TaskDocument.search")
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

    @patch("apps.tasks.elasticsearch_documents.CommentDocument.search")
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
