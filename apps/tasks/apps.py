from django.apps.config import AppConfig
from elasticsearch_dsl import connections

from tms.settings import ELASTIC_HOSTS


class TasksConfig(AppConfig):
    name = "apps.tasks"

    def ready(self):
        import apps.tasks.signals  # noqa: F401

        connections.create_connection(hosts=ELASTIC_HOSTS[0])
