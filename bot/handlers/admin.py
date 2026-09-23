from dataclasses import dataclass, field
from datetime import datetime

from telebot import TeleBot, types
from telebot.apihelper import ApiTelegramException
from telebot.formatting import apply_html_entities

from bot.database.repository import UserRepository
from bot.editors import EditorRepository
from bot.groups import GROUPS, SEST1, SEST2
from bot.handlers.common import send_homework
from bot.services.homework_service import HomeworkService
from bot.utils.dates import parse_admin_datetime
from bot.utils.formatting import (
    MAX_MESSAGE_LENGTH,
    format_announcement,
    format_homework,
    format_notify_message,
)


SUBJECTS = (
    "Алгоритмы и структуры данных",
    "Линейная алгебра",
    "English Composition",
    "АЧиП",
    "Управление проектами",
    "АВД",
    "ООП",
    "Математика для МО",
    "Основы МО",
    "Основы веб-разработки",
    "Манасоведение",
)


# Database cleanup:
# .\.venv\Scripts\python.exe -c "from bot.utils.development import clear_current_database; print(clear_current_database())"

@dataclass
class AdminState:
    action: str
    step: str
    group_name: str | None = None
    homework_id: int | None = None
    values: dict = field(default_factory=dict)


def register_admin_handlers(
    bot: TeleBot,
    service: HomeworkService,
    admin_ids: frozenset[int],
    users: UserRepository,
    editors: EditorRepository,
) -> None:
    states: dict[int, AdminState] = {}

    def is_head_admin(user_id: int) -> bool:
        return user_id in admin_ids

    def editor_group(user_id: int) -> str | None:
        if is_head_admin(user_id):
            return SEST2
        if user_id in editors.list_ids():
            return SEST1
        return None

    def can_manage_group(user_id: int, group_name: str) -> bool:
        return group_name in GROUPS and (
            is_head_admin(user_id) or editor_group(user_id) == group_name
        )

    def deny(message) -> None:
        bot.send_message(message.chat.id, "У вас нет прав для этой команды.")
#  bot.send_message(message.chat.id, "You have no access to this command.")

    def prompt_for_step(chat_id: int, state: AdminState) -> None:
        prompts = {
            "subject": "Выберите предмет из списка ниже или введите его название вручную.",
#          "subject": "Enter subject.\n\nExample:\nMachine Learning",
            "description": "Введите описание задания (можно прикрепить ссылки или отправить фото с описанием в подписи).\n\nПример:\nПрочитать главу 4 и решить задачи 12–18.",
#          "description": "Enter homework description (you can attach links or send a photo with description in caption).\n\nExample:\nRead chapter 4 and solve problems 12–18.",
            "photo": "Отправьте новую фотографию для задания или напишите /delete_photo для удаления фото." if state.action == "edit" else "Отправьте фотографию к заданию (или отправьте /skip, если фото не требуется):",
#          "photo": "Send a new photo for the homework or send /delete_photo to remove photo." if state.action == "edit" else "Send a photo for the homework (or send /skip if no photo is needed):",
            "start_at": f"Введите дату начала.\n\nПример:\n2026-11-03\n\nСегодня: <code>{service.current_time():%Y-%m-%d}</code>\n\nМожно указать время: 2026-11-03 09:00",
#          "start_at": "Enter start date.\n\nExample:\n2026-11-03\n\nYou can specify time: 2026-11-03 09:00",
            "deadline": "Введите срок сдачи.\n\nПример:\n2026-11-04 23:59\n\nЕсли указать только дату, срок будет установлен на 23:59.",
#          "deadline": "Enter deadline.\n\nExample:\n2026-11-04 23:59\n\nIf only date is specified, deadline will be set to 23:59.",
        }
        reply_markup = None
        if state.action == "share" and state.step == "subject":
            reply_markup = types.InlineKeyboardMarkup()
            for index, subject in enumerate(SUBJECTS):
                reply_markup.add(
                    types.InlineKeyboardButton(
                        subject,
                        callback_data=f"admin_subject:{index}",
                    )
                )
        bot.send_message(
            chat_id,
            prompts[state.step],
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    @bot.message_handler(commands=["admin"])
    def admin_command(message):
        if editor_group(message.from_user.id) is None:
            deny(message)
            return
        commands = "/share\n/edit\n/delete\n/notify\n/cancel"
        if is_head_admin(message.from_user.id):
            commands += "\n/announcement\n/add_sest1\n/del_sest1"
        bot.send_message(message.chat.id, commands)

    @bot.message_handler(commands=["share"])
    def share_command(message):
        group_name = editor_group(message.from_user.id)
        if group_name is None:
            deny(message)
            return
        states[message.from_user.id] = AdminState(
            action="share", step="subject", group_name=group_name
        )
        prompt_for_step(message.chat.id, states[message.from_user.id])

    @bot.message_handler(commands=["cancel"])
    def cancel_command(message):
        if editor_group(message.from_user.id) is None:
            deny(message)
            return
        if states.pop(message.from_user.id, None):
            bot.send_message(message.chat.id, "Операция отменена.")
#          bot.send_message(message.chat.id, "Operation cancelled.")
        else:
            bot.send_message(message.chat.id, "Нет незавершённой операции для отмены.")
#          bot.send_message(message.chat.id, "No pending operation to cancel.")

    @bot.message_handler(commands=["edit", "delete"])
    def manage_command(message):
        group_name = editor_group(message.from_user.id)
        if group_name is None:
            deny(message)
            return
        action = message.text.split()[0].lstrip("/").split("@")[0]
        if is_head_admin(message.from_user.id):
            keyboard = types.InlineKeyboardMarkup()
            for candidate in GROUPS:
                keyboard.add(
                    types.InlineKeyboardButton(
                        candidate, callback_data=f"admin_group:{action}:{candidate}"
                    )
                )
            bot.send_message(
                message.chat.id,
                "Выберите группу:",
                reply_markup=keyboard,
            )
        else:
            _show_admin_list(bot, message.chat.id, service, action, group_name, 0)

    @bot.message_handler(commands=["notify"])
    def notify_command(message):
        group_name = editor_group(message.from_user.id)
        if group_name is None:
            deny(message)
            return
        chat_ids = users.list_chat_ids(group_name)
        if not chat_ids:
            bot.send_message(message.chat.id, "Пока нет пользователей, которым можно отправить уведомление.")
#          bot.send_message(message.chat.id, "There are no users to notify yet.")
            return
        subjects = [item.subject for item in service.latest_active(group_name, 3)]
        text = format_notify_message(subjects)
        sent = 0
        for chat_id in chat_ids:
            try:
                bot.send_message(chat_id, text, parse_mode="HTML")
                sent += 1
            except ApiTelegramException as error:
                if error.error_code in {400, 403}:
                    users.delete(chat_id)
        bot.send_message(message.chat.id, f"Уведомление отправлено: {sent} из {len(chat_ids)}.")
#      bot.send_message(message.chat.id, f"Notification sent: {sent} of {len(chat_ids)}.")

    @bot.message_handler(commands=["announcement"])
    def announcement_command(message):
        if not is_head_admin(message.from_user.id):
            deny(message)
            return
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "Все студенты SEST-1-25",
                callback_data=f"admin_announcement:{SEST1}",
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Все студенты SEST-2-25",
                callback_data=f"admin_announcement:{SEST2}",
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Все пользователи", callback_data="admin_announcement:all"
            )
        )
        bot.send_message(
            message.chat.id,
            "Выберите получателей объявления:",
            reply_markup=keyboard,
        )

    @bot.message_handler(commands=["add_sest1", "del_sest1"])
    def manage_editor_command(message):
        if not is_head_admin(message.from_user.id):
            deny(message)
            return
        action = message.text.split()[0].lstrip("/").split("@")[0]
        states[message.from_user.id] = AdminState(
            action=action, step="telegram_id", group_name=SEST1
        )
        verb = "добавить" if action == "add_sest1" else "удалить"
        bot.send_message(
            message.chat.id,
            f"Отправьте Telegram ID редактора, которого нужно {verb}.",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith(("admin_group:", "admin_list:", "admin_pick:", "admin_field:", "admin_delete:", "admin_announcement:", "admin_subject:")))
    def admin_callback(call):
        if editor_group(call.from_user.id) is None:
            bot.answer_callback_query(call.id, "Нет прав доступа.")
#          bot.answer_callback_query(call.id, "Access denied.")
            return
        parts = call.data.split(":")
        if parts[0] == "admin_subject":
            state = states.get(call.from_user.id)
            if not state or state.action != "share" or state.step != "subject":
                bot.answer_callback_query(call.id, "Выбор предмета уже завершён.")
                return
            try:
                subject_index = int(parts[1])
            except (IndexError, ValueError):
                bot.answer_callback_query(call.id, "Неизвестный предмет.")
                return
            if not 0 <= subject_index < len(SUBJECTS):
                bot.answer_callback_query(call.id, "Неизвестный предмет.")
                return
            subject = SUBJECTS[subject_index]
            state.values["subject"] = subject
            state.step = "description"
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None,
            )
            prompt_for_step(call.message.chat.id, state)
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_announcement":
            if not is_head_admin(call.from_user.id):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            target = parts[1]
            if target != "all" and target not in GROUPS:
                bot.answer_callback_query(call.id, "Неизвестная группа.")
                return
            states[call.from_user.id] = AdminState(
                action="announcement", step="announcement_text", group_name=target
            )
            bot.send_message(call.message.chat.id, "Отправьте текст объявления.")
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_group":
            action, group_name = parts[1], parts[2]
            if not can_manage_group(call.from_user.id, group_name):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            _show_admin_list(
                bot, call.message.chat.id, service, action, group_name, 0
            )
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_list":
            action, group_name, page = parts[1], parts[2], int(parts[3])
            if not can_manage_group(call.from_user.id, group_name):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            _show_admin_list(bot, call.message.chat.id, service, action, group_name, page, edit_message=call.message)
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_pick":
            action, group_name, homework_id = parts[1], parts[2], int(parts[3])
            if not can_manage_group(call.from_user.id, group_name):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            homework = service.repository.get(homework_id, group_name)
            if not homework:
                bot.answer_callback_query(call.id, "Задание уже удалено.")
#              bot.answer_callback_query(call.id, "Homework has already been deleted.")
                return
            if action == "delete":
                keyboard = types.InlineKeyboardMarkup()
                keyboard.row(
                    types.InlineKeyboardButton("Да, удалить", callback_data=f"admin_delete:yes:{group_name}:{homework_id}"),
#                  types.InlineKeyboardButton("Yes, delete", callback_data=f"admin_delete:yes:{homework_id}"),
                    types.InlineKeyboardButton("Отмена", callback_data=f"admin_delete:no:{group_name}:0"),
#                  types.InlineKeyboardButton("Cancel", callback_data="admin_delete:no:0"),
                )
                bot.send_message(call.message.chat.id, "Удалить это задание?\n\n" + format_homework(homework), parse_mode="HTML", reply_markup=keyboard)
#              bot.send_message(call.message.chat.id, "Delete this homework?\n\n" + format_homework(homework), parse_mode="HTML", reply_markup=keyboard)
            else:
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                for key, label in (("subject", "Предмет"), ("description", "Описание"), ("photo", "Фотография"), ("start_at", "Дата начала"), ("deadline", "Срок сдачи")):
#              for key, label in (("subject", "Subject"), ("description", "Description"), ("photo", "Photo"), ("start_at", "Start date"), ("deadline", "Deadline")):
                    keyboard.add(types.InlineKeyboardButton(label, callback_data=f"admin_field:{group_name}:{homework_id}:{key}"))
                bot.send_message(call.message.chat.id, "Выберите, что изменить:", reply_markup=keyboard)
#              bot.send_message(call.message.chat.id, "Select what to edit:", reply_markup=keyboard)
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_field":
            group_name, homework_id, field_name = parts[1], int(parts[2]), parts[3]
            if not can_manage_group(call.from_user.id, group_name):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            states[call.from_user.id] = AdminState(
                action="edit", step=field_name, group_name=group_name,
                homework_id=homework_id,
            )
            prompt_for_step(call.message.chat.id, states[call.from_user.id])
            bot.answer_callback_query(call.id)
            return
        if parts[0] == "admin_delete":
            group_name, homework_id = parts[2], int(parts[3])
            if not can_manage_group(call.from_user.id, group_name):
                bot.answer_callback_query(call.id, "Нет прав доступа.")
                return
            if parts[1] == "yes" and service.repository.delete(homework_id, group_name):
                bot.send_message(call.message.chat.id, "Домашнее задание удалено.")
#              bot.send_message(call.message.chat.id, "Homework deleted.")
            else:
                bot.send_message(call.message.chat.id, "Удаление отменено.")
#              bot.send_message(call.message.chat.id, "Deletion cancelled.")
            bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda message: message.from_user and message.from_user.id in states, content_types=["text", "photo"])
    def admin_input(message):
        state = states.get(message.from_user.id)
        if not state:
            return
        if message.content_type == "text" and message.text.startswith("/") and not message.text.startswith(("/skip", "/delete_photo")):
            return
        if state.action in {"add_sest1", "del_sest1"}:
            if not is_head_admin(message.from_user.id):
                states.pop(message.from_user.id, None)
                deny(message)
                return
            try:
                editor_id = int((message.text or "").strip())
                if editor_id <= 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "Telegram ID должен быть положительным числом.")
                return
            changed = editors.add(editor_id) if state.action == "add_sest1" else editors.remove(editor_id)
            states.pop(message.from_user.id, None)
            if state.action == "add_sest1":
                text = "Редактор SEST-1-25 добавлен." if changed else "Этот пользователь уже является редактором SEST-1-25."
            else:
                text = "Редактор SEST-1-25 удалён." if changed else "Этот пользователь не является редактором SEST-1-25."
            bot.send_message(message.chat.id, text)
            return
        if state.action == "announcement":
            if not is_head_admin(message.from_user.id):
                states.pop(message.from_user.id, None)
                deny(message)
                return
            raw_text = (message.text or "").strip()
            if message.content_type != "text" or not raw_text:
                bot.send_message(message.chat.id, "Текст объявления не может быть пустым.")
                return
            announcement_text = format_announcement(
                apply_html_entities(message.text, message.entities).strip()
            )
            if len(announcement_text) > MAX_MESSAGE_LENGTH:
                bot.send_message(message.chat.id, "Объявление слишком длинное. Сократите текст.")
                return
            if state.group_name == "all":
                chat_ids = users.list_all_chat_ids()
            elif state.group_name in GROUPS:
                chat_ids = users.list_chat_ids(state.group_name)
            else:
                states.pop(message.from_user.id, None)
                bot.send_message(message.chat.id, "Не удалось определить получателей.")
                return
            states.pop(message.from_user.id, None)
            if not chat_ids:
                bot.send_message(message.chat.id, "Пока нет пользователей, которым можно отправить объявление.")
                return
            sent = 0
            for chat_id in chat_ids:
                try:
                    bot.send_message(chat_id, announcement_text, parse_mode="HTML")
                    sent += 1
                except ApiTelegramException as error:
                    if error.error_code in {400, 403}:
                        users.delete(chat_id)
            bot.send_message(
                message.chat.id,
                f"Объявление отправлено: {sent} из {len(chat_ids)}.",
            )
            return
        if not state.group_name or not can_manage_group(message.from_user.id, state.group_name):
            states.pop(message.from_user.id, None)
            deny(message)
            return
        if state.action == "edit":
            _save_edit_value(bot, message, service, states, state, prompt_for_step)
            return
        _save_share_value(bot, message, service, states, state, prompt_for_step)


def _show_admin_list(
    bot: TeleBot,
    chat_id,
    service: HomeworkService,
    action: str,
    group_name: str,
    page: int,
    edit_message=None,
) -> None:
    items = service.repository.list_all(group_name)
    if not items:
        service_text = "Домашних заданий пока нет."
#      service_text = "No homework yet."
        if edit_message:
            # Telegram permits editing text but not changing an empty keyboard reliably in all clients.
            bot.edit_message_text(service_text, chat_id, edit_message.message_id)
        else:
            bot.send_message(chat_id, service_text)
        return
    per_page = 8
    keyboard = types.InlineKeyboardMarkup()
    for item in items[page * per_page:(page + 1) * per_page]:
        label = f"{item.subject} – до {item.deadline.strftime('%d.%m.%Y')}"
#      label = f"{item.subject} – until {item.deadline.strftime('%d.%m.%Y')}"
        keyboard.add(types.InlineKeyboardButton(label[:64], callback_data=f"admin_pick:{action}:{group_name}:{item.id}"))
    nav = []
    if page:
        nav.append(types.InlineKeyboardButton("‹ Назад", callback_data=f"admin_list:{action}:{group_name}:{page - 1}"))
#      nav.append(types.InlineKeyboardButton("‹ Back", callback_data=f"admin_list:{action}:{page - 1}"))
    if (page + 1) * per_page < len(items):
        nav.append(types.InlineKeyboardButton("Далее ›", callback_data=f"admin_list:{action}:{group_name}:{page + 1}"))
#      nav.append(types.InlineKeyboardButton("Next ›", callback_data=f"admin_list:{action}:{page + 1}"))
    if nav:
        keyboard.row(*nav)
    text = "Выберите задание для изменения:" if action == "edit" else "Выберите задание для удаления:"
#  text = "Select homework to edit:" if action == "edit" else "Select homework to delete:"
    if edit_message:
        bot.edit_message_text(text, chat_id, edit_message.message_id, reply_markup=keyboard)
    else:
        bot.send_message(chat_id, text, reply_markup=keyboard)


def _save_share_value(bot: TeleBot, message, service: HomeworkService, states: dict, state: AdminState, prompt_for_step) -> None:
    if state.step == "subject":
        if message.content_type != "text" or not message.text.strip():
            bot.send_message(message.chat.id, "Введите предмет текстом.")
#          bot.send_message(message.chat.id, "Enter subject as text.")
            return
        state.values["subject"] = message.text.strip()
        state.step = "description"
        prompt_for_step(message.chat.id, state)
        return

    if state.step == "description":
        if message.content_type == "photo":
            raw_text = (message.caption or "").strip()
            if not raw_text:
                bot.send_message(message.chat.id, "Вы отправили фото без описания. Пожалуйста, отправьте описание текстом или прикрепите фото с описанием в подписи.")
#              bot.send_message(message.chat.id, "You sent a photo without a description. Please send description as text or attach photo with description in caption.")
                return
            state.values["description"] = apply_html_entities(message.caption, message.caption_entities).strip()
            state.values["photo_id"] = message.photo[-1].file_id
            state.step = "start_at"
            prompt_for_step(message.chat.id, state)
            return
        else:
            raw_text = (message.text or "").strip()
            if not raw_text:
                bot.send_message(message.chat.id, "Описание не может быть пустым. Попробуйте ещё раз.")
#              bot.send_message(message.chat.id, "Description cannot be empty. Try again.")
                return
            state.values["description"] = apply_html_entities(message.text, message.entities).strip()
            state.step = "photo"
            prompt_for_step(message.chat.id, state)
            return

    if state.step == "photo":
        if message.content_type == "photo":
            state.values["photo_id"] = message.photo[-1].file_id
            state.step = "start_at"
            prompt_for_step(message.chat.id, state)
            return
        else:
            text = (message.text or "").strip().casefold()
            if text in {"/skip", "skip", "пропустить", "нет", "-"}:
                state.values["photo_id"] = None
                state.step = "start_at"
                prompt_for_step(message.chat.id, state)
                return
            bot.send_message(message.chat.id, "Отправьте фотографию или команду /skip, чтобы продолжить без фото.")
#          bot.send_message(message.chat.id, "Send a photo or /skip command to proceed without a photo.")
            return

    if state.step == "start_at":
        if message.content_type != "text" or not message.text.strip():
            bot.send_message(message.chat.id, "Введите дату начала текстом.")
#          bot.send_message(message.chat.id, "Enter start date as text.")
            return
        try:
            parsed = parse_admin_datetime(message.text.strip(), is_deadline=False)
        except ValueError:
            bot.send_message(message.chat.id, "Неверный формат даты. Используйте, например: 2026-11-03")
#          bot.send_message(message.chat.id, "Invalid datetime format. Use something like: 2026-11-03")
            return
        state.values["start_at"] = parsed
        state.step = "deadline"
        prompt_for_step(message.chat.id, state)
        return

    if state.step == "deadline":
        if message.content_type != "text" or not message.text.strip():
            bot.send_message(message.chat.id, "Введите срок сдачи текстом.")
#          bot.send_message(message.chat.id, "Enter deadline as text.")
            return
        try:
            parsed = parse_admin_datetime(message.text.strip(), is_deadline=True)
        except ValueError:
            bot.send_message(message.chat.id, "Неверный формат даты. Используйте, например: 2026-11-04 23:59")
#          bot.send_message(message.chat.id, "Invalid date format. Use, for example: 2026-11-04 23:59")
            return
        if state.values["start_at"] > parsed:
            bot.send_message(message.chat.id, "Дата начала не может быть позже срока сдачи. Введите срок сдачи ещё раз.")
#          bot.send_message(message.chat.id, "Start date cannot be after deadline. Enter deadline again.")
            return
        state.values["deadline"] = parsed
        state.values.setdefault("photo_id", None)
        try:
            homework = service.create_homework(group_name=state.group_name, **state.values)
        except ValueError:
            bot.send_message(message.chat.id, "Дата начала не может быть позже срока сдачи. Введите срок сдачи ещё раз.")
#          bot.send_message(message.chat.id, "Start date cannot be after deadline. Enter deadline again.")
            return
        states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Домашнее задание сохранено:")
#      bot.send_message(message.chat.id, "Homework saved:")
        send_homework(bot, message.chat.id, homework)
        return


def _save_edit_value(bot: TeleBot, message, service: HomeworkService, states: dict, state: AdminState, prompt_for_step) -> None:
    homework = service.repository.get(state.homework_id, state.group_name)
    if not homework:
        states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Задание не найдено.")
#       bot.send_message(message.chat.id, "Assignment not found.")
        return

    if state.step == "subject":
        if message.content_type != "text" or not message.text.strip():
            bot.send_message(message.chat.id, "Введите предмет текстом.")
#       bot.send_message(message.chat.id, "Enter the name of the subject.")
            return
        updated = service.repository.update(state.homework_id, state.group_name, subject=message.text.strip())
        states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Домашнее задание обновлено:")
#       bot.send_message(message.chat.id, "Homework updated:")
        send_homework(bot, message.chat.id, updated)
        return

    if state.step == "description":
        if message.content_type == "photo":
            raw_text = (message.caption or "").strip()
            if not raw_text:
                bot.send_message(message.chat.id, "Вы отправили фото без описания. Отправьте описание текстом или фото с описанием в подписи.")
#               bot.send_message(message.chat.id, "You sent an image with no description. Send the description as text or a captioned image.")
                return
            desc_html = apply_html_entities(message.caption, message.caption_entities).strip()
            photo_id = message.photo[-1].file_id
            updated = service.repository.update(state.homework_id, state.group_name, description=desc_html, photo_id=photo_id)
        else:
            raw_text = (message.text or "").strip()
            if not raw_text:
                bot.send_message(message.chat.id, "Описание не может быть пустым.")
#               bot.send_message(message.chat.id, "Description can't be empty.")
                return
            desc_html = apply_html_entities(message.text, message.entities).strip()
            updated = service.repository.update(state.homework_id, state.group_name, description=desc_html)
        states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Домашнее задание обновлено:")
#       bot.send_message(message.chat.id, "Homework updated:")
        send_homework(bot, message.chat.id, updated)
        return

    if state.step == "photo":
        if message.content_type == "photo":
            photo_id = message.photo[-1].file_id
            updated = service.repository.update(state.homework_id, state.group_name, photo_id=photo_id)
            states.pop(message.from_user.id, None)
            bot.send_message(message.chat.id, "Фотография обновлена:")
#           bot.send_message(message.chat.id, "Image updated:")
            send_homework(bot, message.chat.id, updated)
            return
        else:
            text = (message.text or "").strip().casefold()
            if text in {"/delete_photo", "удалить", "/delete", "delete"}:
                updated = service.repository.update(state.homework_id, state.group_name, photo_id=None)
                states.pop(message.from_user.id, None)
                bot.send_message(message.chat.id, "Фотография удалена:")
#               bot.send_message(message.chat.id, "Image deleted:")
                send_homework(bot, message.chat.id, updated)
                return
            bot.send_message(message.chat.id, "Отправьте фотографию или напишите /delete_photo для удаления фото.")
#           bot.send_message(message.chat.id, "Send a new image or type /delete_photo to remove it.")
            return

    if state.step in {"start_at", "deadline"}:
        if message.content_type != "text" or not message.text.strip():
            bot.send_message(message.chat.id, "Введите дату текстом.")
#           bot.send_message(message.chat.id, "Send the date in text.")
            return
        try:
            field_value = parse_admin_datetime(message.text.strip(), is_deadline=state.step == "deadline")
        except ValueError:
            bot.send_message(message.chat.id, "Неверный формат даты. Используйте, например: 2026-11-04 23:59")
#           bot.send_message(message.chat.id, "Wrong datetime format. Use something like: 2026-11-04 23:59")
            return
        start_at = field_value if state.step == "start_at" else homework.start_at
        deadline = field_value if state.step == "deadline" else homework.deadline
        if start_at > deadline:
            bot.send_message(message.chat.id, "Дата начала не может быть позже срока сдачи. Попробуйте ещё раз.")
#           bot.send_message(message.chat.id, "Start date cannot be after deadline. Enter deadline again.")
            return
        updated = service.repository.update(state.homework_id, state.group_name, **{state.step: field_value})
        states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Домашнее задание обновлено:")
#       bot.send_message(message.chat.id, "Homework updated:")
        send_homework(bot, message.chat.id, updated)
        return
