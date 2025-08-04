from django.db.models import Q, QuerySet, Sum

from apps.common.helpers import get_previous_month_range_utc
from apps.tasks.models.tasks import Task


class TaskService:
    @staticmethod
    def get_top_logged_tasks_last_month(limit: int) -> QuerySet:
        start_of_last_month, end_of_last_month = get_previous_month_range_utc()

        return (
            Task.objects.filter(
                Q(
                    time_logs__start_time__gte=start_of_last_month,
                    time_logs__end_time__lte=end_of_last_month,
                )
                | Q(
                    time_logs__date__gte=start_of_last_month,
                    time_logs__date__lte=end_of_last_month,
                )
            )
            .annotate(total_minutes=Sum("time_logs__duration_minutes"))
            .filter(total_minutes__gt=0)
            .order_by("-total_minutes")
            .only("id", "title")[:limit]
        )
