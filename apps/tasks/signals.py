import logging

from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from apps.tasks.elasticsearch_documents import TaskDocument, CommentDocument
from apps.tasks.models import Task, Comment

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Task)
def create_or_update_task_document(sender: str, instance: Task, created: bool, **kwargs):
    if created:
        TaskDocument(
            meta={"id": instance.id},
            title=instance.title,
            description=instance.description,
            assignee=instance.assignee.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        ).save()
    else:
        doc = TaskDocument.get(id=instance.id)
        doc.update(
            title=instance.title,
            description=instance.description,
            assignee=instance.assignee.id,
            status=instance.status,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )
        doc.save()


@receiver(post_delete, sender=Task)
def delete_task_document(sender: str, instance: Task, **kwargs):
    doc = TaskDocument.get(id=instance.id)
    doc.delete()


@receiver(post_save, sender=Comment)
def create_or_update_comment_document(sender: str, instance: Comment, created: bool, **kwargs):
    if created:
        CommentDocument(
            meta={"id": instance.id},
            text=instance.text,
            task=instance.task.id,
            author=instance.author.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        ).save()
    else:
        doc = CommentDocument.get(id=instance.id)
        doc.update(
            text=instance.text,
            task=instance.task.id,
            author=instance.author.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )
        doc.save()


@receiver(post_delete, sender=Comment)
def delete_comment_document(sender: str, instance: Comment, **kwargs):  # ← исправлено
    doc = CommentDocument.get(id=instance.id)
    doc.delete()
