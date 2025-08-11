import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tms.settings")

app = Celery("tms")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    "top_tasks_report": {
        "task": "apps.tasks.tasks.top_tasks_by_logged_time_report",
        "schedule": crontab(minute=0, hour=0, day_of_week=1),
    }
}
