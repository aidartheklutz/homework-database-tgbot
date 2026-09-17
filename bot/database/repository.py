from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from bot.database.database import Database
from bot.groups import is_valid_group


@dataclass(frozen=True)
class Homework:
    id: int
    subject: str
    description: str
    start_at: datetime
    deadline: datetime
    created_at: datetime
    updated_at: datetime | None
    group_name: str
    photo_id: str | None = None


def _to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _row_to_homework(row) -> Homework:
    return Homework(
        id=row["id"], subject=row["subject"], description=row["description"],
        start_at=_to_datetime(row["start_at"]), deadline=_to_datetime(row["deadline"]),
        created_at=_to_datetime(row["created_at"]), updated_at=_to_datetime(row["updated_at"]),
        group_name=row["group_name"],
        photo_id=row["photo_id"] if "photo_id" in row.keys() else None,
    )


class HomeworkRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, subject: str, description: str, start_at: datetime, deadline: datetime, group_name: str, photo_id: str | None = None) -> Homework:
        if not is_valid_group(group_name):
            raise ValueError("invalid_group")
        created_at = datetime.now().replace(microsecond=0)
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO homework(subject, description, photo_id, start_at, deadline, created_at, group_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (subject, description, photo_id, start_at.isoformat(sep=" "), deadline.isoformat(sep=" "), created_at.isoformat(sep=" "), group_name),
            )
            row = connection.execute("SELECT * FROM homework WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_homework(row)

    def get(self, homework_id: int, group_name: str) -> Homework | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM homework WHERE id = ? AND group_name = ?",
                (homework_id, group_name),
            ).fetchone()
        return _row_to_homework(row) if row else None

    def list_all(self, group_name: str) -> list[Homework]:
        return self._query(
            "SELECT * FROM homework WHERE group_name = ? ORDER BY deadline, id",
            (group_name,),
        )

    def list_active(self, now: datetime, group_name: str) -> list[Homework]:
        return self._query(
            "SELECT * FROM homework WHERE group_name = ? AND start_at <= ? AND deadline >= ? ORDER BY deadline, id",
            (group_name, now.isoformat(sep=" "), now.isoformat(sep=" ")),
        )

    def list_historical(self, now: datetime, group_name: str) -> list[Homework]:
        return self._query(
            "SELECT * FROM homework WHERE group_name = ? AND deadline < ? ORDER BY deadline DESC, id",
            (group_name, now.isoformat(sep=" ")),
        )

    def list_deadline_on(self, day_start: datetime, day_end: datetime, group_name: str, historical_only: bool = False) -> list[Homework]:
        sql = "SELECT * FROM homework WHERE group_name = ? AND deadline >= ? AND deadline < ?"
        values: tuple = (group_name, day_start.isoformat(sep=" "), day_end.isoformat(sep=" "))
        if historical_only:
            sql += " AND deadline < ?"
            values += (datetime.now().isoformat(sep=" "),)
        return self._query(sql + " ORDER BY deadline, id", values)

    def list_by_deadline_month(self, year: int, month: int, now: datetime, historical: bool, group_name: str) -> list[Homework]:
        prefix = f"{year:04d}-{month:02d}"
        condition = "deadline < ?" if historical else "start_at <= ? AND deadline >= ?"
        values = (group_name, prefix + "%", now.isoformat(sep=" ")) if historical else (group_name, prefix + "%", now.isoformat(sep=" "), now.isoformat(sep=" "))
        return self._query(f"SELECT * FROM homework WHERE group_name = ? AND deadline LIKE ? AND {condition} ORDER BY deadline, id", values)

    def update(self, homework_id: int, group_name: str, **fields) -> Homework | None:
        allowed = {key: value for key, value in fields.items() if key in {"subject", "description", "photo_id", "start_at", "deadline"}}
        if not allowed:
            return self.get(homework_id, group_name)
        parts, values = [], []
        for key, value in allowed.items():
            parts.append(f"{key} = ?")
            values.append(value.isoformat(sep=" ") if isinstance(value, datetime) else value)
        parts.append("updated_at = ?")
        values.append(datetime.now().replace(microsecond=0).isoformat(sep=" "))
        values.extend((homework_id, group_name))
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE homework SET {', '.join(parts)} WHERE id = ? AND group_name = ?",
                values,
            )
        return self.get(homework_id, group_name)

    def delete(self, homework_id: int, group_name: str) -> bool:
        with self.database.connect() as connection:
            return connection.execute(
                "DELETE FROM homework WHERE id = ? AND group_name = ?",
                (homework_id, group_name),
            ).rowcount > 0

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

    def get_group(self, chat_id: int) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT group_name FROM users WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return row["group_name"] if row else None

    def set_group(self, chat_id: int, group_name: str) -> None:
        if not is_valid_group(group_name):
            raise ValueError("invalid_group")
        self.upsert(chat_id)
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE users SET group_name = ? WHERE chat_id = ?", (group_name, chat_id)
            )

    def list_chat_ids(self, group_name: str) -> list[int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT chat_id FROM users WHERE group_name = ? ORDER BY chat_id",
                (group_name,),
            ).fetchall()
        return [row["chat_id"] for row in rows]

    def delete(self, chat_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
