from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker


class Command(BaseCommand):
    help = "Generates users"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="How many records to add")

    def handle(self, *args, **options):
        fake = Faker()
        count = options["count"]
        users_to_create = []
        for _ in range(count):
            user = User(username=fake.unique.user_name(), email=fake.unique.email(), password="1234")
            users_to_create.append(user)

        with transaction.atomic():
            User.objects.bulk_create(users_to_create, batch_size=1000)
        self.stdout.write(self.style.SUCCESS("Users have been created."))
