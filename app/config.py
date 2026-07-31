from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ENV_PATHS = (Path(".env"), Path(".env.example"))
DEFAULT_REALTORS_PATH = Path("config/realtors.json")
DEFAULT_SUBSCRIBERS_PATH = Path("data/subscribers.json")


@dataclass(frozen=True)
class RealtorBinding:
    full_name: str
    telegram_id: str | None = None
    delivery_mode: str = "links"
    custom_message: str | None = None


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    google_docs_url: str
    admin_ids: set[str]
    realtors_path: Path
    subscribers_path: Path
    poll_interval_seconds: int = 3


def load_config() -> AppConfig:
    load_env_files()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    docs_url = os.getenv("GOOGLE_DOCS_URL", "").strip()
    admin_ids = parse_csv_set(os.getenv("TELEGRAM_ADMIN_IDS", ""))
    legacy_target_id = os.getenv("TELEGRAM_TARGET_ID", "").strip()

    if legacy_target_id:
        admin_ids.add(legacy_target_id)

    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("GOOGLE_DOCS_URL", docs_url),
        )
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {joined}")

    return AppConfig(
        telegram_bot_token=token,
        google_docs_url=docs_url,
        admin_ids=admin_ids,
        realtors_path=Path(os.getenv("REALTORS_CONFIG_PATH", DEFAULT_REALTORS_PATH)),
        subscribers_path=Path(
            os.getenv("SUBSCRIBERS_PATH", DEFAULT_SUBSCRIBERS_PATH)
        ),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "3")),
    )


def load_realtor_bindings(path: Path) -> list[RealtorBinding]:
    data = json.loads(path.read_text(encoding="utf-8"))
    bindings = []
    for item in data.get("realtors", []):
        full_name = str(item.get("full_name", "")).strip()
        telegram_id_raw = str(item.get("telegram_id", "")).strip()
        delivery_mode = str(item.get("delivery_mode", "links")).strip() or "links"
        custom_message = str(item.get("custom_message", "")).strip() or None
        if not full_name:
            continue
        bindings.append(
            RealtorBinding(
                full_name=full_name,
                telegram_id=telegram_id_raw or None,
                delivery_mode=delivery_mode,
                custom_message=custom_message,
            )
        )
    return bindings


def parse_csv_set(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def load_env_files() -> None:
    for path in DEFAULT_ENV_PATHS:
        if not path.exists():
            continue

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
