import logging

import telebot

from bot.config import load_settings
from bot.database.database import Database
from bot.database.repository import HomeworkRepository
from bot.handlers.admin import register_admin_handlers
from bot.handlers.homework import register_homework_handlers
from bot.services.homework_service import HomeworkService


def create_bot():
    settings = load_settings()
    database = Database(settings.database_path)
    database.initialize()
    service = HomeworkService(HomeworkRepository(database), settings.timezone)
    bot = telebot.TeleBot(settings.bot_token)
    register_homework_handlers(bot, service)
    register_admin_handlers(bot, service, settings.admin_ids)
    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_bot().infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()