from rest_framework import serializers

from tms.tasks.models.comments import Comment


class CommentRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("text", "task", "author")


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = (
            "text",
            "task",
        )
