from bot.config import load_settings
from bot.database.database import Database
from bot.database.repository import HomeworkRepository


def clear_homework_database(repository: HomeworkRepository) -> int:
    """Remove all homework records and return the number of deleted records."""
    return repository.delete_all()


def clear_current_database() -> int:
    """Remove homework from the database configured in .env.

    This is a development helper and is intentionally not a Telegram command.
    """
    settings = load_settings()
    database = Database(settings.database_path)
    database.initialize()
    return clear_homework_database(HomeworkRepository(database))
