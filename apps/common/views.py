from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.helpers import EmptySerializer


class HealthView(GenericAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = EmptySerializer

    @staticmethod
    def get(request: Request) -> Response:
        return Response({"live": True})


class ProtectedTestView(GenericAPIView):
    serializer_class = EmptySerializer

    @staticmethod
    def get(request: Request) -> Response:
        return Response({"live": True})


class MultiSerializerMixin:
    multi_serializer_class: dict[str, type[serializers.Serializer]] | None = None

    def get_serializer_class(self):
        if self.multi_serializer_class and self.action in self.multi_serializer_class:
            return self.multi_serializer_class[self.action]
        return self.serializer_class
