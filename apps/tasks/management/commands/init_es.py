import time

from django.core.management.base import BaseCommand
from elastic_transport import ConnectionError
from elasticsearch_dsl import connections

from apps.tasks.elasticsearch_documents import TaskDocument
from tms.settings import ELASTIC_HOSTS


class Command(BaseCommand):
    help = "Initialize Elasticsearch indixes for tasks and comments"

    def handle(self, *args, **options):
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            try:
                self.stdout.write(f"[{attempt}] Connecting to Elasticsearch...")
                connections.create_connection(hosts=ELASTIC_HOSTS[0])
                TaskDocument.init()
                self.stdout.write(self.style.SUCCESS("Elasticsearch indices initialized."))
                break
            except ConnectionError as e:
                self.stderr.write(self.style.WARNING(f"[{attempt}] Elasticsearch not ready: {e}"))
                if attempt == max_attempts:
                    self.stderr.write(self.style.ERROR("Giving up after 10 attempts."))
                    raise
                time.sleep(5)
