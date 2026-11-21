"""Clinic clocks are stored in UTC and shown in Asia/Kolkata."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    KOLKATA = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    KOLKATA = timezone(timedelta(hours=5, minutes=30))


def as_kolkata(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KOLKATA)


def clinic_day(value: datetime) -> date:
    return as_kolkata(value).date()


def clinic_wall_now() -> datetime:
    """Current clinic time without a timezone, matching how appointments are stored."""
    return datetime.now(KOLKATA).replace(tzinfo=None)


def clinic_period_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive clinic dates as a half-open UTC range."""
    start_local = datetime.combine(start, time.min).replace(tzinfo=KOLKATA)
    end_local = datetime.combine(end + timedelta(days=1), time.min).replace(tzinfo=KOLKATA)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def format_clinic_stamp(value: datetime | None) -> str:
    if value is None:
        return ""
    local = as_kolkata(value)
    hour = local.hour % 12 or 12
    suffix = "am" if local.hour < 12 else "pm"
    return f"{local.strftime('%d %B, %Y')}, {hour}:{local.minute:02d} {suffix}"
