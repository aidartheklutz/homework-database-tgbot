from telebot import TeleBot, types

from bot.database.repository import UserRepository
from bot.groups import GROUPS, is_valid_group
from bot.handlers.common import HELP_TEXT, TRACKED_CONTENT_TYPES


def start_text(group_name: str | None) -> str:
    selected = group_name if is_valid_group(group_name) else "Не выбрано"
    return f"<b>SESTHomeworkBot</b>\nВыбранная группа: {selected}\n\n{HELP_TEXT}"


def group_button() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Выбрать группу", callback_data="choose_group"))
    return keyboard


def send_start(bot: TeleBot, chat_id: int, users: UserRepository) -> None:
    bot.send_message(
        chat_id,
        start_text(users.get_group(chat_id)),
        parse_mode="HTML",
        reply_markup=group_button(),
    )


def register_onboarding_handlers(bot: TeleBot, users: UserRepository) -> None:
    @bot.message_handler(commands=["start"])
    def start_command(message):
        send_start(bot, message.chat.id, users)

    @bot.callback_query_handler(func=lambda call: call.data == "choose_group")
    def choose_group(call):
        keyboard = types.InlineKeyboardMarkup()
        for group_name in GROUPS:
            keyboard.add(
                types.InlineKeyboardButton(
                    group_name, callback_data=f"set_group:{group_name}"
                )
            )
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "<b>Выберите группу:</b>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_group:"))
    def set_group(call):
        group_name = call.data.partition(":")[2]
        if not is_valid_group(group_name):
            bot.answer_callback_query(call.id, "Неизвестная группа.")
            return
        users.set_group(call.message.chat.id, group_name)
        bot.answer_callback_query(call.id, f"Выбрана группа {group_name}")
        send_start(bot, call.message.chat.id, users)

    def needs_group(message) -> bool:
        return bool(
            message.chat
            and message.chat.type == "private"
            and not is_valid_group(users.get_group(message.chat.id))
        )

    @bot.message_handler(func=needs_group, content_types=TRACKED_CONTENT_TYPES)
    def require_group(message):
        send_start(bot, message.chat.id, users)
