from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.views import RegisterUserView, UserListView, UserMonthlyLoggedTimeView

urlpatterns = [
    path("register", RegisterUserView.as_view(), name="users-register"),
    path("token", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("logged-time/last-month", UserMonthlyLoggedTimeView.as_view(), name="users-logged-time-last-month"),
    path("", UserListView.as_view(), name="users-list"),
]
