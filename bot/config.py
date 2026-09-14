import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    database_path: Path
    timezone: ZoneInfo


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured")

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    try:
        admin_ids = frozenset(int(item.strip()) for item in raw_admin_ids.split(",") if item.strip())
    except ValueError as error:
        raise RuntimeError("ADMIN_IDS must contain numeric Telegram user IDs") from error
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS is not configured")

    timezone_name = os.getenv("TIMEZONE", "Asia/Bishkek")
    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        database_path=Path(os.getenv("DATABASE_PATH", "homework.db")),
        timezone=ZoneInfo(timezone_name),
    )
