from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.views import MultiSerializerMixin
from apps.tasks.models import TimeLog
from apps.tasks.serializers import (
    TimeLogSerializer,
    TimeLogSpecificDateSerializer,
    TimeLogStartSerializer,
    TimeLogStopSerializer,
)


class TimeLogView(MultiSerializerMixin, ListModelMixin, DestroyModelMixin, GenericViewSet):
    queryset = TimeLog.objects.all()
    serializer_class = TimeLogSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["task"]
    multi_serializer_class = {
        "start_timer": TimeLogStartSerializer,
        "stop_timer": TimeLogStopSerializer,
        "log_date": TimeLogSpecificDateSerializer,
    }

    @action(detail=False, methods=["post"], url_path="start-timer")
    def start_timer(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TimeLog.objects.filter(start_time__isnull=False, end_time=None).update(
            end_time=serializer.validated_data["start_time"]
        )
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["patch"], url_path="stop-timer")
    def stop_timer(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="log-date")
    def log_date(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
