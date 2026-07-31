from __future__ import annotations

import argparse
import time

from app.config import AppConfig, RealtorBinding, load_config, load_realtor_bindings
from app.google_docs import fetch_document_text
from app.parser import extract_realtor_leads
from app.subscribers import Subscriber, load_subscribers, upsert_subscriber
from app.telegram_client import TelegramUpdate, get_updates, send_message


ADMIN_BROADCAST_BUTTON = "Отправить заявки"
ADMIN_STATUS_BUTTON = "Сколько подписчиков"
USER_HELP_BUTTON = "Что умеет бот"


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

    if text.startswith("/start"):
        handle_start(config, bindings, update)
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
    if binding is not None:
        upsert_subscriber(
            config.subscribers_path,
            Subscriber(
                chat_id=update.chat_id,
                realtor_name=binding.full_name,
                username=update.username,
                first_name=update.first_name,
            ),
        )

    is_admin = update.chat_id in config.admin_ids
    send_message(
        config.telegram_bot_token,
        update.chat_id,
        format_start_message(binding, is_admin),
        reply_keyboard=build_keyboard(is_admin),
    )


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


def build_keyboard(is_admin: bool) -> list[list[str]] | None:
    keyboard = [[USER_HELP_BUTTON]]
    if is_admin:
        keyboard.insert(0, [ADMIN_BROADCAST_BUTTON, ADMIN_STATUS_BUTTON])
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


if __name__ == "__main__":
    raise SystemExit(main())
