from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdminState:
    mode: str | None = None


def load_admin_states(path: Path) -> dict[str, AdminState]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    states: dict[str, AdminState] = {}
    for chat_id, item in data.get("admins", {}).items():
        mode = str(item.get("mode", "")).strip() or None
        states[str(chat_id)] = AdminState(mode=mode)
    return states


def load_admin_state(path: Path, chat_id: str) -> AdminState:
    return load_admin_states(path).get(chat_id, AdminState())


def save_admin_state(path: Path, chat_id: str, state: AdminState) -> None:
    states = load_admin_states(path)
    if state.mode:
        states[chat_id] = state
    else:
        states.pop(chat_id, None)

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "admins": {key: asdict(value) for key, value in states.items()}
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
