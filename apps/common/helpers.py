from datetime import UTC, datetime, timedelta

from rest_framework import serializers


class EmptySerializer(serializers.Serializer):
    pass


def get_previous_month_range_utc() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    first_day_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_previous_month = first_day_current_month - timedelta(seconds=1)
    first_day_previous_month = last_day_previous_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_day_previous_month, last_day_previous_month
