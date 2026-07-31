from __future__ import annotations

import argparse
import time

from app.admin_state import AdminState, load_admin_state, save_admin_state
from app.config import (
    AppConfig,
    RealtorBinding,
    load_config,
    load_realtor_bindings,
    save_realtor_bindings,
)
from app.google_docs import fetch_document_text
from app.parser import extract_realtor_leads
from app.subscribers import Subscriber, load_subscribers, upsert_subscriber
from app.telegram_client import TelegramUpdate, get_updates, send_message


ADMIN_BROADCAST_BUTTON = "Отправить заявки"
ADMIN_STATUS_BUTTON = "Сколько подписчиков"
ADMIN_ADD_REALTOR_BUTTON = "Добавить риэлтора"
ADMIN_CANCEL_BUTTON = "Отмена"
USER_HELP_BUTTON = "Что умеет бот"
ADMIN_STATE_ADD_REALTOR = "add_realtor"


def format_leads_message(realtor_name: str, links: list[str]) -> str:
    return "\n".join(links)


def format_no_access_message() -> str:
    return (
        "Ваш номер пока не привязан к риэлтору. "
        "Когда привязка появится, бот сможет отправлять ваши ссылки."
    )


def format_start_message(binding: RealtorBinding | None, is_admin: bool) -> str:
    if binding is None:
        return format_no_access_message()

    parts = [f"Подписка включена: {binding.full_name}."]
    parts.append("Когда админ запустит рассылку, бот отправит все найденные ссылки.")
    if is_admin:
        parts.append("Для вас открыта админ-панель.")
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("poll", "broadcast-once"),
        default="poll",
    )
    args = parser.parse_args()

    config = load_config()
    bindings = load_realtor_bindings(config.realtors_path)

    if args.mode == "broadcast-once":
        broadcast_updates(config, bindings)
        return 0

    run_polling_bot(config, bindings)
    return 0


def run_polling_bot(config: AppConfig, bindings: list[RealtorBinding]) -> None:
    offset: int | None = None
    while True:
        updates = get_updates(
            config.telegram_bot_token,
            offset=offset,
            timeout_seconds=25,
        )
        for update in updates:
            offset = update.update_id + 1
            handle_update(config, bindings, update)
        time.sleep(config.poll_interval_seconds)


def handle_update(
    config: AppConfig,
    bindings: list[RealtorBinding],
    update: TelegramUpdate,
) -> None:
    text = update.text.strip()
    if not text:
        return

    admin_state = load_admin_state(config.admin_state_path, update.chat_id)

    if text.startswith("/start"):
        handle_start(config, bindings, update)
        return

    if text == ADMIN_CANCEL_BUTTON and update.chat_id in config.admin_ids:
        save_admin_state(config.admin_state_path, update.chat_id, AdminState())
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            "Действие отменено.",
            reply_keyboard=build_keyboard(True),
        )
        return

    if update.chat_id in config.admin_ids and admin_state.mode == ADMIN_STATE_ADD_REALTOR:
        handle_add_realtor_input(config, bindings, update)
        return

    if text == ADMIN_BROADCAST_BUTTON and update.chat_id in config.admin_ids:
        delivered_recipients = broadcast_updates(config, bindings)
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            format_broadcast_result_message(delivered_recipients),
            reply_keyboard=build_keyboard(update.chat_id in config.admin_ids),
        )
        return

    if text == ADMIN_STATUS_BUTTON and update.chat_id in config.admin_ids:
        subscribers = load_subscribers(config.subscribers_path)
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            format_admin_status_message(bindings, subscribers),
            reply_keyboard=build_keyboard(update.chat_id in config.admin_ids),
        )
        return

    if text == ADMIN_ADD_REALTOR_BUTTON and update.chat_id in config.admin_ids:
        save_admin_state(
            config.admin_state_path,
            update.chat_id,
            AdminState(mode=ADMIN_STATE_ADD_REALTOR),
        )
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            (
                "Отправьте одной строкой:\n"
                "ФИО - Telegram ID\n\n"
                "Пример:\n"
                "Иванов Иван Иванович - 123456789\n\n"
                "Если ID пока нет:\n"
                "Иванов Иван Иванович - пока нет ID"
            ),
            reply_keyboard=build_keyboard(True, is_waiting_for_input=True),
        )
        return

    if text == USER_HELP_BUTTON:
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            "Нажмите /start, чтобы включить подписку. Когда админ запустит рассылку, бот пришлет все найденные ссылки.",
            reply_keyboard=build_keyboard(update.chat_id in config.admin_ids),
        )
        return

    send_message(
        config.telegram_bot_token,
        update.chat_id,
        "Используйте кнопки ниже или команду /start.",
        reply_keyboard=build_keyboard(update.chat_id in config.admin_ids),
    )


def handle_start(
    config: AppConfig,
    bindings: list[RealtorBinding],
    update: TelegramUpdate,
) -> None:
    binding = find_binding_by_chat_id(bindings, update.chat_id)
    subscriber: Subscriber | None = None
    if binding is not None:
        subscriber = Subscriber(
            chat_id=update.chat_id,
            realtor_name=binding.full_name,
            username=update.username,
            first_name=update.first_name,
        )
        upsert_subscriber(config.subscribers_path, subscriber)

    is_admin = update.chat_id in config.admin_ids
    send_message(
        config.telegram_bot_token,
        update.chat_id,
        format_start_message(binding, is_admin),
        reply_keyboard=build_keyboard(is_admin),
    )

    if binding is not None and subscriber is not None:
        notify_admins_about_authorization(config, subscriber)


def broadcast_updates(
    config: AppConfig,
    bindings: list[RealtorBinding],
) -> list[str]:
    document_text = fetch_document_text(config.google_docs_url)
    subscribers = load_subscribers(config.subscribers_path)
    if not subscribers:
        return []

    delivered_recipients: list[str] = []
    for subscriber in subscribers:
        binding = find_binding_by_chat_id(bindings, subscriber.chat_id)
        realtor_name = binding.full_name if binding is not None else subscriber.realtor_name
        if binding is not None and binding.delivery_mode == "custom_message":
            message_text = binding.custom_message
            if not message_text:
                continue
            send_message(
                config.telegram_bot_token,
                subscriber.chat_id,
                message_text,
            )
            delivered_recipients.append(format_broadcast_recipient(subscriber, realtor_name))
            continue

        leads = extract_realtor_leads(document_text, realtor_name)
        if not leads.links:
            continue
        send_message(
            config.telegram_bot_token,
            subscriber.chat_id,
            format_leads_message(leads.realtor_name, leads.links),
        )
        delivered_recipients.append(format_broadcast_recipient(subscriber, realtor_name))
    return delivered_recipients


def find_binding_by_chat_id(
    bindings: list[RealtorBinding],
    chat_id: str,
) -> RealtorBinding | None:
    for binding in bindings:
        if binding.telegram_id and binding.telegram_id == chat_id:
            return binding
    return None


def build_keyboard(
    is_admin: bool,
    is_waiting_for_input: bool = False,
) -> list[list[str]] | None:
    keyboard = [[USER_HELP_BUTTON]]
    if is_admin:
        keyboard.insert(0, [ADMIN_BROADCAST_BUTTON, ADMIN_STATUS_BUTTON])
        keyboard.insert(1, [ADMIN_ADD_REALTOR_BUTTON])
    if is_waiting_for_input:
        keyboard.insert(0, [ADMIN_CANCEL_BUTTON])
    return keyboard


def format_admin_status_message(
    bindings: list[RealtorBinding],
    subscribers: list[Subscriber],
) -> str:
    authorized_chat_ids = {subscriber.chat_id for subscriber in subscribers}
    authorized_count = 0
    lines = []

    for index, binding in enumerate(bindings, start=1):
        if not binding.telegram_id:
            lines.append(f"{index}. {binding.full_name} — нет Telegram ID")
            continue

        is_authorized = binding.telegram_id in authorized_chat_ids
        if is_authorized:
            authorized_count += 1
        if is_authorized:
            subscriber = next(
                item for item in subscribers if item.chat_id == binding.telegram_id
            )
            status = f"авторизовался ({format_subscriber_identity(subscriber)})"
        else:
            status = "не авторизовался"
        lines.append(f"{index}. {binding.full_name} — {status}")

    total_count = len(bindings)
    header = f"Подключено: {authorized_count} из {total_count}."
    if not lines:
        return f"{header}\nСписок риэлторов пока пуст."
    return header + "\n\n" + "\n".join(lines)


def format_subscriber_identity(subscriber: Subscriber) -> str:
    if subscriber.username:
        return f"@{subscriber.username}"
    if subscriber.first_name:
        return f"{subscriber.first_name}, ID {subscriber.chat_id}"
    return f"ID {subscriber.chat_id}"


def format_broadcast_result_message(delivered_recipients: list[str]) -> str:
    delivered_count = len(delivered_recipients)
    if not delivered_recipients:
        return "Готово. Сообщений отправлено: 0."
    return (
        f"Готово. Сообщений отправлено: {delivered_count}.\n\n"
        + "\n".join(
            f"{index}. {recipient}"
            for index, recipient in enumerate(delivered_recipients, start=1)
        )
    )


def format_broadcast_recipient(subscriber: Subscriber, realtor_name: str) -> str:
    return f"{realtor_name} -> {format_subscriber_identity(subscriber)}"


def notify_admins_about_authorization(
    config: AppConfig,
    subscriber: Subscriber,
) -> None:
    message = format_admin_authorization_message(subscriber)
    for admin_id in config.admin_ids:
        send_message(config.telegram_bot_token, admin_id, message)


def format_admin_authorization_message(subscriber: Subscriber) -> str:
    lines = [
        "Новая авторизация в боте.",
        f"Риэлтор: {subscriber.realtor_name}",
        f"Telegram: {format_subscriber_identity(subscriber)}",
    ]
    return "\n".join(lines)


def handle_add_realtor_input(
    config: AppConfig,
    bindings: list[RealtorBinding],
    update: TelegramUpdate,
) -> None:
    parsed = parse_realtor_input(update.text)
    if parsed is None:
        send_message(
            config.telegram_bot_token,
            update.chat_id,
            (
                "Не смог распознать строку.\n"
                "Нужен формат: ФИО - Telegram ID\n"
                "Или: ФИО - пока нет ID"
            ),
            reply_keyboard=build_keyboard(True, is_waiting_for_input=True),
        )
        return

    full_name, telegram_id = parsed
    new_binding = RealtorBinding(full_name=full_name, telegram_id=telegram_id)

    updated = False
    for index, binding in enumerate(bindings):
        if binding.full_name.casefold() == full_name.casefold():
            bindings[index] = RealtorBinding(
                full_name=full_name,
                telegram_id=telegram_id,
                delivery_mode=binding.delivery_mode,
                custom_message=binding.custom_message,
            )
            updated = True
            break

    if not updated:
        bindings.append(new_binding)

    save_realtor_bindings(config.realtors_path, bindings)
    save_admin_state(config.admin_state_path, update.chat_id, AdminState())

    action = "обновлен" if updated else "добавлен"
    id_text = telegram_id or "пока без Telegram ID"
    send_message(
        config.telegram_bot_token,
        update.chat_id,
        f"Риэлтор {action}.\n{full_name}\n{id_text}",
        reply_keyboard=build_keyboard(True),
    )


def parse_realtor_input(text: str) -> tuple[str, str | None] | None:
    normalized = text.replace("—", "-").replace("–", "-")
    if " - " not in normalized:
        return None

    full_name, raw_telegram_id = normalized.split(" - ", 1)
    full_name = full_name.strip("* ").strip()
    raw_telegram_id = raw_telegram_id.strip("* ").strip()
    if not full_name:
        return None

    lowered = raw_telegram_id.casefold()
    if lowered in {"пока нет id", "нет id", "без id", "пока нет"}:
        return full_name, None

    digits_only = "".join(char for char in raw_telegram_id if char.isdigit())
    if not digits_only:
        return None

    return full_name, digits_only


if __name__ == "__main__":
    raise SystemExit(main())
