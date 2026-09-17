from telebot import TeleBot

from bot.database.repository import Homework, UserRepository
from bot.utils.formatting import format_homework, split_message

TRACKED_CONTENT_TYPES = [
    "text",
    "photo",
    "document",
    "audio",
    "video",
    "voice",
    "sticker",
    "animation",
    "video_note",
    "location",
    "contact",
]


def send_long(bot: TeleBot, chat_id: int, text: str, **kwargs) -> None:
    for chunk in split_message(text):
        bot.send_message(chat_id, chunk, **kwargs)


def send_homework(bot: TeleBot, chat_id: int, homework: Homework) -> None:
    text = format_homework(homework)
    if homework.photo_id:
        if len(text) <= 1024:
            bot.send_photo(chat_id, photo=homework.photo_id, caption=text, parse_mode="HTML")
        else:
            bot.send_photo(chat_id, photo=homework.photo_id)
            send_long(bot, chat_id, text, parse_mode="HTML")
    else:
        send_long(bot, chat_id, text, parse_mode="HTML")


def register_user_tracking(bot: TeleBot, users: UserRepository) -> None:
    def remember(message) -> bool:
        if message.chat and message.chat.type == "private":
            users.upsert(message.chat.id)
        return False

    @bot.message_handler(func=remember, content_types=TRACKED_CONTENT_TYPES)
    def _remember_user(message):
        pass


HELP_TEXT = """<b>Список команд</b>

✱ <b>/today</b> – задания, которые нужно сдать сегодня.
✱ <b>/tmrw</b> – задания, которые нужно сдать завтра.
✱ <b>/active</b> – список актуальных заданий.
✱ <b>/active all</b> – показать все актуальные задания.
✱ <b>/history</b> – просмотреть архив прошедших заданий.
 ↳ <b>/history ГГГГ-ММ-ДД</b> – просмотреть прошедшие задания на определённую дату.
✱ <b>/about</b> – информация о проекте.
"""
#  HELP_TEXT = """<b>Homework</b>
#  
#  /today – homework due today.
#  /tmrw – homework due tomorrow.
#  /active – list of active homework.
#  /active all – show all active homework.
#  /history – view past homework archive.
#  
#  ADMIN: /share, /edit, /delete, /cancel."""



# Дополнительно (additionally):
# /history 2026-04-11 – все прошедшие задания за дату.
# /history 2026-04-11 – all past homework for the date.

# /history 2026-04-11 Математика, Физика – задания только по указанным предметам.
# /history 2026-04-11 Math, Physics – homework only for specified subjects.
