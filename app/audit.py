from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"
_lock = threading.Lock()
_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")
_LONG_DIGITS = re.compile(r"\d{9,}")


def mask(value: Any, limit: int = 120) -> Any:
    if isinstance(value, str):
        text = _EMAIL.sub(r"\1***@\2", value)
        text = _LONG_DIGITS.sub("***", text)
        return text if len(text) <= limit else text[: limit - 1] + "..."
    if isinstance(value, dict):
        return {k: mask(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v, limit) for v in value]
    return value


def record(event: str, run_id: str, actor: str, **fields: Any) -> None:
    """Append one masked line to the audit trail. Ids and decisions only, no message text."""
    line = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "run_id": run_id,
        "actor": actor,
        **{k: mask(v) for k, v in fields.items()},
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock, AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
