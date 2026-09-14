from telebot import TeleBot

from bot.database.repository import Homework
from bot.utils.formatting import format_homework, split_message


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


HELP_TEXT = """<b>Домашние задания</b>

/today – задания, которые нужно сдать сегодня.
/tmrw – задания, которые нужно сдать завтра.
/active – список актуальных заданий.
/active all – показать все актуальные задания.
/history – просмотреть архив прошедших заданий.

ADMIN: /share, /edit, /delete, /cancel."""
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
