from django_minio_backend import MinioBackend
from urllib3.exceptions import MaxRetryError

from tms.settings import MINIO_PUBLIC_ENDPOINT, MINIO_URL_EXPIRY_HOURS


class PublicMinioBackend(MinioBackend):
    def url(self, name):
        client = self.client if self.same_endpoints else self.client_external

        if self.is_bucket_public:
            return f"{MINIO_PUBLIC_ENDPOINT}/{self.bucket}/{name}"

        try:
            u: str = client.presigned_get_object(
                bucket_name=self.bucket, object_name=name, expires=MINIO_URL_EXPIRY_HOURS
            )
            return u
        except MaxRetryError as err:
            raise ConnectionError(
                "Couldn't connect to Minio. Check django_minio_backend parameters in Django-Settings"
            ) from err
