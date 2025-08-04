from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from rest_framework import generics, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.helpers import get_previous_month_range_utc
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


class UserMonthlyLoggedTimeView(APIView):
    def get(self, request: Request) -> Response:
        start_of_last_month, end_of_last_month = get_previous_month_range_utc()
        time_logs: QuerySet = request.user.time_logs.filter(
            Q(
                start_time__gte=start_of_last_month,
                end_time__lte=end_of_last_month,
            )
            | Q(
                date__gte=start_of_last_month,
                date__lte=end_of_last_month,
            )
        )
        total_minutes = time_logs.aggregate(total_minutes=Sum("duration_minutes"))["total_minutes"] or 0

        return Response({"total_minutes": total_minutes}, status.HTTP_200_OK)
