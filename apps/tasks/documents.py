from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from apps.tasks.models import Comment, Task


@registry.register_document
class TaskDocument(Document):
    assignee = fields.KeywordField(attr="assignee_id")

    class Index:
        name = "tasks"

    class Django:
        model = Task
        fields = [
            "title",
            "description",
            "status",
        ]


@registry.register_document
class CommentDocument(Document):
    task = fields.KeywordField(attr="task_id")
    author = fields.KeywordField(attr="author_id")

    class Index:
        name = "comments"

    class Django:
        model = Comment
        fields = [
            "text",
        ]
