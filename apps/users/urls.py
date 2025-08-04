from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.views import RegisterUserView, UserListView, UserMonthlyLoggedTimeView

urlpatterns = [
    path("register", RegisterUserView.as_view(), name="token_register"),
    path("token", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("logged-time/last-month", UserMonthlyLoggedTimeView.as_view(), name="logged_time_last_month"),
    path("", UserListView.as_view(), name="user_list"),
]
