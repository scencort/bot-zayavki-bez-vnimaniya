from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Subscriber:
    chat_id: str
    realtor_name: str
    username: str | None = None
    first_name: str | None = None


def load_subscribers(path: Path) -> list[Subscriber]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    subscribers = []
    for item in data.get("subscribers", []):
        chat_id = str(item.get("chat_id", "")).strip()
        realtor_name = str(item.get("realtor_name", "")).strip()
        username = _coerce_optional(item.get("username"))
        first_name = _coerce_optional(item.get("first_name"))
        if chat_id and realtor_name:
            subscribers.append(
                Subscriber(
                    chat_id=chat_id,
                    realtor_name=realtor_name,
                    username=username,
                    first_name=first_name,
                )
            )
    return subscribers


def save_subscribers(path: Path, subscribers: list[Subscriber]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"subscribers": [asdict(item) for item in subscribers]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_subscriber(path: Path, subscriber: Subscriber) -> None:
    subscribers = load_subscribers(path)
    by_chat_id = {item.chat_id: item for item in subscribers}
    by_chat_id[subscriber.chat_id] = subscriber
    ordered = sorted(by_chat_id.values(), key=lambda item: item.chat_id)
    save_subscribers(path, ordered)


def _coerce_optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
