from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from bot.database.database import Database


@dataclass(frozen=True)
class Homework:
    id: int
    subject: str
    description: str
    start_at: datetime
    deadline: datetime
    created_at: datetime
    updated_at: datetime | None
    photo_id: str | None = None


def _to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _row_to_homework(row) -> Homework:
    return Homework(
        id=row["id"], subject=row["subject"], description=row["description"],
        start_at=_to_datetime(row["start_at"]), deadline=_to_datetime(row["deadline"]),
        created_at=_to_datetime(row["created_at"]), updated_at=_to_datetime(row["updated_at"]),
        photo_id=row["photo_id"] if "photo_id" in row.keys() else None,
    )


class HomeworkRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, subject: str, description: str, start_at: datetime, deadline: datetime, photo_id: str | None = None) -> Homework:
        created_at = datetime.now().replace(microsecond=0)
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO homework(subject, description, photo_id, start_at, deadline, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (subject, description, photo_id, start_at.isoformat(sep=" "), deadline.isoformat(sep=" "), created_at.isoformat(sep=" ")),
            )
            row = connection.execute("SELECT * FROM homework WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_homework(row)

    def get(self, homework_id: int) -> Homework | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM homework WHERE id = ?", (homework_id,)).fetchone()
        return _row_to_homework(row) if row else None

    def list_all(self) -> list[Homework]:
        return self._query("SELECT * FROM homework ORDER BY deadline, id")

    def list_active(self, now: datetime) -> list[Homework]:
        return self._query(
            "SELECT * FROM homework WHERE start_at <= ? AND deadline >= ? ORDER BY deadline, id",
            (now.isoformat(sep=" "), now.isoformat(sep=" ")),
        )

    def list_historical(self, now: datetime) -> list[Homework]:
        return self._query("SELECT * FROM homework WHERE deadline < ? ORDER BY deadline DESC, id", (now.isoformat(sep=" "),))

    def list_deadline_on(self, day_start: datetime, day_end: datetime, historical_only: bool = False) -> list[Homework]:
        sql = "SELECT * FROM homework WHERE deadline >= ? AND deadline < ?"
        values: tuple = (day_start.isoformat(sep=" "), day_end.isoformat(sep=" "))
        if historical_only:
            sql += " AND deadline < ?"
            values += (datetime.now().isoformat(sep=" "),)
        return self._query(sql + " ORDER BY deadline, id", values)

    def list_by_deadline_month(self, year: int, month: int, now: datetime, historical: bool) -> list[Homework]:
        prefix = f"{year:04d}-{month:02d}"
        condition = "deadline < ?" if historical else "start_at <= ? AND deadline >= ?"
        values = (prefix + "%", now.isoformat(sep=" ")) if historical else (prefix + "%", now.isoformat(sep=" "), now.isoformat(sep=" "))
        return self._query(f"SELECT * FROM homework WHERE deadline LIKE ? AND {condition} ORDER BY deadline, id", values)

    def update(self, homework_id: int, **fields) -> Homework | None:
        allowed = {key: value for key, value in fields.items() if key in {"subject", "description", "photo_id", "start_at", "deadline"}}
        if not allowed:
            return self.get(homework_id)
        parts, values = [], []
        for key, value in allowed.items():
            parts.append(f"{key} = ?")
            values.append(value.isoformat(sep=" ") if isinstance(value, datetime) else value)
        parts.append("updated_at = ?")
        values.append(datetime.now().replace(microsecond=0).isoformat(sep=" "))
        values.append(homework_id)
        with self.database.connect() as connection:
            connection.execute(f"UPDATE homework SET {', '.join(parts)} WHERE id = ?", values)
        return self.get(homework_id)

    def delete(self, homework_id: int) -> bool:
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM homework WHERE id = ?", (homework_id,)).rowcount > 0

    def delete_all(self) -> int:
        """Delete every homework record. Intended for development-only cleanup."""
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM homework").rowcount

    def _query(self, query: str, values: Iterable = ()) -> list[Homework]:
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(values)).fetchall()
        return [_row_to_homework(row) for row in rows]


class UserRepository:
    def __init__(self, database: Database):
        self.database = database

    def upsert(self, chat_id: int) -> None:
        now = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users(chat_id, first_seen, last_seen) VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET last_seen = excluded.last_seen
                """,
                (chat_id, now, now),
            )

    def list_chat_ids(self) -> list[int]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT chat_id FROM users ORDER BY chat_id").fetchall()
        return [row["chat_id"] for row in rows]

    def delete(self, chat_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
