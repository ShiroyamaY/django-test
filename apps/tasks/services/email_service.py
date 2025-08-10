import logging

from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from tms import settings

logger = logging.getLogger("apps.tasks")


class EmailService:
    @classmethod
    def send_mail(cls, subject: str, template: str, to: list[str], context=None):
        try:
            html_content = render_to_string(template, context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to,
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            return True

        except Exception as error:
            logger.error(f"Email Service: Error while sending email: {error}")
            return False
