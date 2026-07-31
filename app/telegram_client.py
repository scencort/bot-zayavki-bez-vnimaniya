from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    chat_id: str
    text: str
    username: str | None = None
    first_name: str | None = None


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    reply_keyboard: list[list[str]] | None = None,
    timeout_seconds: int = 30,
) -> None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_keyboard:
        payload["reply_markup"] = {
            "keyboard": [[{"text": item} for item in row] for row in reply_keyboard],
            "resize_keyboard": True,
        }

    _call_api(bot_token, "sendMessage", payload, timeout_seconds=timeout_seconds)


def get_updates(
    bot_token: str,
    offset: int | None = None,
    timeout_seconds: int = 30,
) -> list[TelegramUpdate]:
    payload: dict[str, Any] = {
        "timeout": timeout_seconds,
        "allowed_updates": ["message"],
    }
    if offset is not None:
        payload["offset"] = offset

    data = _call_api(bot_token, "getUpdates", payload, timeout_seconds=timeout_seconds + 5)
    updates = []
    for item in data:
        message = item.get("message") or {}
        chat = message.get("chat") or {}
        text = message.get("text")
        if not text:
            continue
        from_user = message.get("from") or {}
        updates.append(
            TelegramUpdate(
                update_id=int(item["update_id"]),
                chat_id=str(chat.get("id", "")),
                text=str(text),
                username=_coerce_optional(from_user.get("username")),
                first_name=_coerce_optional(from_user.get("first_name")),
            )
        )
    return updates


def _call_api(
    bot_token: str,
    method: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> Any:
    endpoint = f"https://api.telegram.org/bot{bot_token}/{method}"
    body = urlencode(_flatten_payload(payload), doseq=True).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Telegram API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("Could not reach Telegram API") from exc

    if not response_data.get("ok"):
        description = response_data.get("description", "Unknown Telegram API error")
        raise RuntimeError(f"Telegram API error: {description}")

    return response_data.get("result")


def _flatten_payload(payload: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            flattened[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            flattened[key] = "true" if value else "false"
        else:
            flattened[key] = str(value)
    return flattened


def _coerce_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
