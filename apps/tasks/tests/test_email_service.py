import logging
from unittest.mock import patch

from django.core.mail.message import EmailMultiAlternatives
from django.template.exceptions import TemplateDoesNotExist, TemplateSyntaxError
from rest_framework.test import APITestCase

from apps.tasks.services.email_service import EmailService


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
