import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from apps.tasks.models import Task, TimeLog

fake = Faker()


class Command(BaseCommand):
    help = "Generates timelogs"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="How many records to add")

    def handle(self, *args, **options):
        count = options["count"]

        users = list(get_user_model().objects.all()[:100])
        tasks = list(Task.objects.all()[:500])

        if not users or not tasks:
            self.stdout.write(self.style.ERROR("There must be users and tasks in the database."))
            return

        logs = []

        for _ in range(count):
            task = random.choice(tasks)
            user = task.assignee or random.choice(users)
            log = TimeLog(
                task=task,
                user=user,
                date=fake.date_between(start_date="-60d", end_date="today"),
                duration_minutes=random.choice([30, 60, 90, 120]),
            )
            logs.append(log)

        self.stdout.write(f"Creating {len(logs)} TimeLog records...")

        with transaction.atomic():
            TimeLog.objects.bulk_create(logs, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"{len(logs)} records successfully created."))
