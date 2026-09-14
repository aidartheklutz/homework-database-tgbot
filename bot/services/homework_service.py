from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bot.database.repository import Homework, HomeworkRepository
from bot.utils.dates import date_bounds, now_in_timezone
from bot.utils.formatting import normalize_subject


@dataclass(frozen=True)
class HistoryRequest:
    requested_date: date
    subjects: list[str]


def parse_history_arguments(arguments: str) -> HistoryRequest:
    pieces = arguments.strip().split(None, 1)
    if not pieces:
        raise ValueError("missing date")
    from bot.utils.dates import parse_iso_date
    requested_date = parse_iso_date(pieces[0])
    subjects = []
    if len(pieces) == 2:
        unique = set()
        for item in pieces[1].split(","):
            normalized = normalize_subject(item)
            if normalized and normalized not in unique:
                unique.add(normalized)
                subjects.append(normalized)
    return HistoryRequest(requested_date, subjects)


class HomeworkService:
    def __init__(self, repository: HomeworkRepository, timezone: ZoneInfo):
        self.repository = repository
        self.timezone = timezone

    def current_time(self) -> datetime:
        return now_in_timezone(self.timezone)

    def create_homework(self, subject: str, description: str, start_at: datetime, deadline: datetime, photo_id: str | None = None) -> Homework:
        if start_at > deadline:
            raise ValueError("start_after_deadline")
        return self.repository.create(subject.strip(), description.strip(), start_at, deadline, photo_id=photo_id)

    def active_homework(self) -> list[Homework]:
        return self.repository.list_active(self.current_time())

    def latest_active(self, limit: int = 3) -> list[Homework]:
        items = self.active_homework()
        items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return items[:limit]

    def due_on(self, target_date: date) -> list[Homework]:
        start, end = date_bounds(target_date)
        return self.repository.list_deadline_on(start, end)

    def historical_on(self, target_date: date) -> list[Homework]:
        start, end = date_bounds(target_date)
        now = self.current_time()
        return [item for item in self.repository.list_deadline_on(start, end) if item.deadline < now]

    def historical_for_request(self, request: HistoryRequest) -> list[Homework]:
        items = self.historical_on(request.requested_date)
        if not request.subjects:
            return items
        wanted = set(request.subjects)
        return [item for item in items if normalize_subject(item.subject) in wanted]

    def active_months(self) -> list[tuple[int, int]]:
        return self._months_from(self.active_homework())

    def historical_months(self) -> list[tuple[int, int]]:
        return self._months_from(self.repository.list_historical(self.current_time()))

    def active_for_month(self, year: int, month: int) -> list[Homework]:
        return self.repository.list_by_deadline_month(year, month, self.current_time(), historical=False)

    def historical_for_month(self, year: int, month: int) -> list[Homework]:
        return self.repository.list_by_deadline_month(year, month, self.current_time(), historical=True)

    @staticmethod
    def _months_from(items: list[Homework]) -> list[tuple[int, int]]:
        return sorted({(item.deadline.year, item.deadline.month) for item in items}, reverse=True)
