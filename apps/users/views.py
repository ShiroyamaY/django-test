from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.permissions import ReadOnly
from apps.users.serializers import UserListSerializer, UserSerializer


class RegisterUserView(GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        user = User.objects.create_user(**validated_data)

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": self.serializer_class(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = (ReadOnly,)
