from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from apps.common.views import MultiSerializerMixin
from apps.tasks.models import Attachment
from apps.tasks.serializers import AttachmentCreateSerializer, AttachmentListSerializer


class AttachmentView(MultiSerializerMixin, ListModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Attachment.objects.all()
    serializer_class = AttachmentListSerializer
    multi_serializer_class = {
        "create": AttachmentCreateSerializer,
        "list": AttachmentListSerializer,
    }
    parser_classes = (MultiPartParser, JSONParser)
