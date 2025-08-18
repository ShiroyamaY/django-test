from django.apps.config import AppConfig


class TasksConfig(AppConfig):
    name = "apps.tasks"

    def ready(self):
        import apps.tasks.receivers  # noqa: F401
