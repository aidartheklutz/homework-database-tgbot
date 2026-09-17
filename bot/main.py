import logging

import telebot

from bot.config import load_settings
from bot.database.database import Database
from bot.database.repository import HomeworkRepository, UserRepository
from bot.editors import EditorRepository
from bot.handlers.admin import register_admin_handlers
from bot.handlers.common import register_user_tracking
from bot.handlers.homework import register_fallback_handler, register_homework_handlers
from bot.handlers.onboarding import register_onboarding_handlers
from bot.services.homework_service import HomeworkService


def create_bot():
    settings = load_settings()
    database = Database(settings.database_path)
    database.initialize()
    homework_repository = HomeworkRepository(database)
    user_repository = UserRepository(database)
    editor_repository = EditorRepository(settings.editors_path)
    service = HomeworkService(homework_repository, settings.timezone)
    bot = telebot.TeleBot(settings.bot_token)
    register_user_tracking(bot, user_repository)
    register_onboarding_handlers(bot, user_repository)
    register_homework_handlers(bot, service, user_repository)
    register_admin_handlers(
        bot, service, settings.admin_ids, user_repository, editor_repository
    )
    register_fallback_handler(bot)
    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_bot().infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()
