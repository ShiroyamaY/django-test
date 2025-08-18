import factory
from factory.django import DjangoModelFactory

from apps.tasks.models import Attachment, Comment, Task, TimeLog
from apps.users.factories import UserFactory


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Faker("sentence", nb_words=4)
    assignee = factory.SubFactory(UserFactory)


class TimeLogFactory(DjangoModelFactory):
    class Meta:
        model = TimeLog

    task = factory.SubFactory(TaskFactory)
    user = factory.SelfAttribute("task.assignee")
    date = factory.Faker("date_object")
    duration_minutes = 60


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment

    text = factory.Faker("text", max_nb_chars=200)
    task = factory.SubFactory(TaskFactory)
    author = factory.SubFactory(UserFactory)


class AttachmentFactory(DjangoModelFactory):
    class Meta:
        model = Attachment

    task = factory.SubFactory(TaskFactory)
    filename = factory.Faker("file_name")
    status = Attachment.Status.PENDING
    object_name = factory.Faker("uuid4")
