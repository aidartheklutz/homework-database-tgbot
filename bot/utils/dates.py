from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

RUSSIAN_MONTHS = ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")


def now_in_timezone(timezone: ZoneInfo) -> datetime:
    return datetime.now(timezone).replace(tzinfo=None, microsecond=0)


def parse_admin_datetime(value: str, is_deadline: bool = False) -> datetime:
    value = value.strip()
    formats = ("%Y-%m-%d %H:%M", "%Y-%m-%d")
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d" and is_deadline:
                return parsed.replace(hour=23, minute=59)
            return parsed
        except ValueError:
            pass
    raise ValueError("invalid datetime")


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def date_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min)
    return start, start + timedelta(days=1)


def russian_month(year: int, month: int) -> str:
    return f"{RUSSIAN_MONTHS[month - 1]} {year}"
