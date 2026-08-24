from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


APP_TIMEZONE = ZoneInfo(settings.app_timezone)


def in_app_timezone(value: datetime) -> datetime:
    """Normalize database datetimes before applying calendar-day rules.

    PostgreSQL returns timezone-aware values. SQLite, used in tests, may remove
    the UTC marker, so naive values are treated as UTC rather than local time.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE)


def is_event_from_previous_day(
    starts_at: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    reference = in_app_timezone(now or datetime.now(timezone.utc))
    return in_app_timezone(starts_at).date() < reference.date()
