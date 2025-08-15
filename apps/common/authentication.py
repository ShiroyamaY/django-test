from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from tms.settings import MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_ATTACHMENTS


class MinioWebhookAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if auth_header == MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_ATTACHMENTS:
            return None, None

        raise AuthenticationFailed("Invalid Minio webhook token")
