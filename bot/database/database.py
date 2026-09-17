import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    photo_id TEXT,
                    start_at DATETIME NOT NULL,
                    deadline DATETIME NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME,
                    group_name TEXT NOT NULL DEFAULT 'SEST-2-25'
                )
                """
            )
            cursor = connection.execute("PRAGMA table_info(homework)")
            columns = {row["name"] for row in cursor.fetchall()}
            if "photo_id" not in columns:
                connection.execute("ALTER TABLE homework ADD COLUMN photo_id TEXT")
            if "group_name" not in columns:
                connection.execute(
                    "ALTER TABLE homework ADD COLUMN group_name TEXT NOT NULL DEFAULT 'SEST-2-25'"
                )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_homework_deadline ON homework(deadline)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_homework_start_at ON homework(start_at)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_homework_group_deadline "
                "ON homework(group_name, deadline)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    first_seen DATETIME NOT NULL,
                    last_seen DATETIME NOT NULL,
                    group_name TEXT
                )
                """
            )
            user_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "group_name" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN group_name TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_name)"
            )
