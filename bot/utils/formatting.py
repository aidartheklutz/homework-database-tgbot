import html
from collections import defaultdict
from datetime import datetime

from bot.database.repository import Homework

MAX_MESSAGE_LENGTH = 3900


def normalize_subject(subject: str) -> str:
    return " ".join(subject.casefold().split())


def display_date(value: datetime) -> str:
    return value.strftime("%d.%m.%Y")


def format_homework(homework: Homework) -> str:
    return f"<b>{html.escape(homework.subject)}</b>\nОт: {display_date(homework.start_at)}\nДо: {display_date(homework.deadline)}\n\n{homework.description}"
#  return f"<b>{html.escape(homework.subject)}</b>\nFrom: {display_date(homework.start_at)}\nTo: {display_date(homework.deadline)}\n\n{homework.description}"


def format_grouped_full(items: list[Homework]) -> str:
    grouped = defaultdict(list)
    for item in items:
        grouped[item.deadline.date()].append(item)
    blocks = []
    for deadline, group in sorted(grouped.items()):
        blocks.append(f"<b>До {deadline.strftime('%d.%m.%Y')}</b>\n\n" + "\n\n".join(format_homework(item) for item in group))
#      blocks.append(f"<b>Until {deadline.strftime('%d.%m.%Y')}</b>\n\n" + "\n\n".join(format_homework(item) for item in group))
    return "\n\n".join(blocks)


def format_history_index(items: list[Homework]) -> str:
    grouped = defaultdict(list)
    for item in items:
        grouped[item.deadline.date()].append(item)
    blocks = []
    for deadline, group in sorted(grouped.items()):
        subjects = "\n".join(item.subject for item in group)
        blocks.append(f"Дедлайн: {deadline.isoformat()}\n{subjects}")
#      blocks.append(f"Deadline: {deadline.isoformat()}\n{subjects}")
    return "\n\n".join(blocks)


def format_notify_message(subjects: list[str]) -> str:
    if not subjects:
        return "Опубликовано новое домашнее задание! Напишите /active для просмотра."
    names = "\n".join(f"<b>{html.escape(subject)}</b>" for subject in subjects)
    return f"Опубликовано новое домашнее задание!\n\n{names}\n\nНапишите /active для просмотра."


def split_message(text: str, maximum: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= maximum:
        return [text]
    chunks, remaining = [], text
    while len(remaining) > maximum:
        split_at = remaining.rfind("\n", 0, maximum)
        if split_at < maximum // 2:
            split_at = maximum
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks
