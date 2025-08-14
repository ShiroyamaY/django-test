from elasticsearch_dsl import Date, Document, Keyword, Text


class TaskDocument(Document):
    title = Text()
    description = Text()
    status = Keyword()
    assignee = Keyword()
    created_at = Date()
    updated_at = Date()

    class Index:
        name = "tasks"


class CommentDocument(Document):
    title = Text()
    task = Keyword()
    author = Keyword()
    created_at = Date()
    updated_at = Date()

    class Index:
        name = "comments"
