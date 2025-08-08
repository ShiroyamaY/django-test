import time
from django.core.management.base import BaseCommand
from apps.tasks.elasticsearch_documents import TaskDocument, CommentDocument
from elasticsearch_dsl import connections
from elastic_transport import ConnectionError

class Command(BaseCommand):
    help = "Initialize Elasticsearch indices for tasks and comments"

    def handle(self, *args, **options):
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            try:
                self.stdout.write(f"[{attempt}] Connecting to Elasticsearch...")
                connections.create_connection(hosts=['http://elastic:password@elastic:9200'])
                TaskDocument.init()
                self.stdout.write(self.style.SUCCESS("Elasticsearch indices initialized."))
                break
            except ConnectionError as e:
                self.stderr.write(self.style.WARNING(
                    f"[{attempt}] Elasticsearch not ready: {e}"
                ))
                if attempt == max_attempts:
                    self.stderr.write(self.style.ERROR("Giving up after 10 attempts."))
                    raise
                time.sleep(5)
