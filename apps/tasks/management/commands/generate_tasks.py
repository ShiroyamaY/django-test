from random import choice

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from apps.tasks.models import Task


class Command(BaseCommand):
    help = "Generates tasks"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="How many records to add")

    def handle(self, *args, **options):
        users = list(User.objects.all()[:100])

        if not users:
            self.stdout.write("No users found to generate tasks, run generate_users command")
            return

        fake = Faker()
        tasks = []
        count = options["count"]
        for _ in range(count):
            task = Task(title=fake.sentence(nb_words=4), assignee=choice(users))
            tasks.append(task)

        with transaction.atomic():
            Task.objects.bulk_create(tasks, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"{len(tasks)} tasks created."))
