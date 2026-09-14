from datetime import timedelta

from telebot import TeleBot, types

from bot.database.repository import Homework
from bot.handlers.common import HELP_TEXT, send_homework, send_long
from bot.services.homework_service import HomeworkService, parse_history_arguments
from bot.utils.dates import russian_month
from bot.utils.formatting import format_grouped_full, format_history_index, format_homework

MONTHS_PER_PAGE = 8


def _month_keyboard(kind: str, months: list[tuple[int, int]], page: int) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    start = page * MONTHS_PER_PAGE
    for year, month in months[start:start + MONTHS_PER_PAGE]:
        keyboard.add(types.InlineKeyboardButton(russian_month(year, month), callback_data=f"{kind}:{year}:{month}"))
    navigation = []
    if page > 0:
        navigation.append(types.InlineKeyboardButton("‹ Назад", callback_data=f"{kind}_page:{page - 1}"))
#      navigation.append(types.InlineKeyboardButton("‹ Back", callback_data=f"{kind}_page:{page - 1}"))
    if start + MONTHS_PER_PAGE < len(months):
        navigation.append(types.InlineKeyboardButton("Далее ›", callback_data=f"{kind}_page:{page + 1}"))
#      navigation.append(types.InlineKeyboardButton("Next ›", callback_data=f"{kind}_page:{page + 1}"))
    if navigation:
        keyboard.row(*navigation)
    return keyboard


def _send_homework_list(bot: TeleBot, chat_id: int, header: str, items: list[Homework]) -> None:
    bot.send_message(chat_id, header, parse_mode="HTML")
    for item in items:
        send_homework(bot, chat_id, item)


def register_homework_handlers(bot: TeleBot, service: HomeworkService) -> None:
    @bot.message_handler(commands=["start", "help"])
    def help_command(message):
        bot.send_message(message.chat.id, HELP_TEXT, parse_mode="HTML")

    @bot.message_handler(commands=["today"])
    def today_command(message):
        items = service.due_on(service.current_time().date())
        if not items:
            bot.send_message(message.chat.id, "На сегодня заданий со сроком сдачи нет.")
#          bot.send_message(message.chat.id, "No homework due today.")
            return
        _send_homework_list(bot, message.chat.id, f"<b>Задания на сегодня</b> (всего: {len(items)}):", items)
#      _send_homework_list(bot, message.chat.id, f"<b>Homework due today</b> (total: {len(items)}):", items)

    @bot.message_handler(commands=["tmrw"])
    def tomorrow_command(message):
        items = service.due_on(service.current_time().date() + timedelta(days=1))
        if not items:
            bot.send_message(message.chat.id, "На завтра заданий со сроком сдачи нет.")
#          bot.send_message(message.chat.id, "No homework due tomorrow.")
            return
        _send_homework_list(bot, message.chat.id, f"<b>Задания на завтра</b> (всего: {len(items)}):", items)
#      _send_homework_list(bot, message.chat.id, f"<b>Homework due tomorrow</b> (total: {len(items)}):", items)

    @bot.message_handler(commands=["active"])
    def active_command(message):
        argument = _command_argument(message.text)
        if argument.casefold() == "all":
            items = service.active_homework()
            if not items:
                bot.send_message(message.chat.id, "Сейчас нет активных домашних заданий.")
#              bot.send_message(message.chat.id, "No active homework right now.")
                return
            _send_homework_list(bot, message.chat.id, f"<b>Все активные задания</b> (всего: {len(items)}):", items)
#          _send_homework_list(bot, message.chat.id, f"<b>All active homework</b> (total: {len(items)}):", items)
            return
        if argument:
            bot.send_message(message.chat.id, "Используйте /active или /active all.")
#          bot.send_message(message.chat.id, "Use /active or /active all.")
            return
        months = service.active_months()
        if not months:
            bot.send_message(message.chat.id, "Сейчас нет активных домашних заданий.")
#          bot.send_message(message.chat.id, "No active homework right now.")
            return
        bot.send_message(message.chat.id, "Выберите месяц с активными заданиями:", reply_markup=_month_keyboard("active", months, 0))
#      bot.send_message(message.chat.id, "Select a month with active homework:", reply_markup=_month_keyboard("active", months, 0))

    @bot.message_handler(commands=["history"])
    def history_command(message):
        argument = _command_argument(message.text)
        if not argument:
            months = service.historical_months()
            if not months:
                bot.send_message(message.chat.id, "Прошедших домашних заданий пока нет.")
#              bot.send_message(message.chat.id, "No past homework yet.")
                return
            bot.send_message(message.chat.id, "Выберите месяц с прошедшими заданиями:", reply_markup=_month_keyboard("history", months, 0))
#          bot.send_message(message.chat.id, "Select a month with past homework:", reply_markup=_month_keyboard("history", months, 0))
            return
        try:
            request = parse_history_arguments(argument)
        except ValueError:
            bot.send_message(message.chat.id, "Используйте дату в формате:\n\n/history 2026-11-04\n\nЧтобы получить задания только по предметам:\n\n/history 2026-11-04 Машинное обучение, Линейная алгебра")
#          bot.send_message(message.chat.id, "Use date in format:\n\n/history 2026-11-04\n\nTo get homework for specific subjects:\n\n/history 2026-11-04 Machine Learning, Linear Algebra")
            return
        items = service.historical_for_request(request)
        if not items:
            bot.send_message(message.chat.id, "За указанную дату подходящих прошедших домашних заданий нет.")
#          bot.send_message(message.chat.id, "No matching past homework for the specified date.")
            return
        _send_homework_list(bot, message.chat.id, f"<b>Прошедшие задания ({request.requested_date.strftime('%d.%m.%Y')})</b> (всего: {len(items)}):", items)
#      _send_homework_list(bot, message.chat.id, f"<b>Past homework ({request.requested_date.strftime('%d.%m.%Y')})</b> (total: {len(items)}):", items)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(("active:", "history:", "active_page:", "history_page:")))
    def month_callback(call):
        kind, *values = call.data.split(":")
        if kind.endswith("_page"):
            base_kind = kind.removesuffix("_page")
            months = service.active_months() if base_kind == "active" else service.historical_months()
            page = int(values[0])
            if not months:
                bot.answer_callback_query(call.id, "Список обновлён.")
#              bot.answer_callback_query(call.id, "List updated.")
                return
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=_month_keyboard(base_kind, months, page))
            bot.answer_callback_query(call.id)
            return
        year, month = int(values[0]), int(values[1])
        items = service.active_for_month(year, month) if kind == "active" else service.historical_for_month(year, month)
        if not items:
            bot.answer_callback_query(call.id, "Для этого месяца заданий больше нет.")
#          bot.answer_callback_query(call.id, "No more homework for this month.")
            return
        bot.answer_callback_query(call.id)
        if kind == "active":
            _send_homework_list(bot, call.message.chat.id, f"<b>{russian_month(year, month)}</b> (заданий: {len(items)}):", items)
#          _send_homework_list(bot, call.message.chat.id, f"<b>{russian_month(year, month)}</b> (homework count: {len(items)}):", items)
        else:
            heading = f"<b>{russian_month(year, month)}</b>\n\n"
            output = format_history_index(items)
            send_long(bot, call.message.chat.id, heading + output, parse_mode="HTML")


def _command_argument(text: str) -> str:
    pieces = text.strip().split(None, 1)
    return pieces[1].strip() if len(pieces) > 1 else ""
