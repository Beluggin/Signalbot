# memory_engine.py
import json
import time
from pathlib import Path

MEMORY_PATH = Path("memory_log.json")
MAX_RECENT = 12

def _load_all():
    if not MEMORY_PATH.exists():
        return []
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_all(rows):
    MEMORY_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

def save_interaction(user_text: str, bot_text: str):
    rows = _load_all()
    rows.append({"ts": time.time(), "user": user_text, "bot": bot_text})
    _save_all(rows)

def load_recent_memory(n: int = MAX_RECENT) -> str:
    rows = _load_all()[-n:]
    if not rows:
        return "(none)"
    # compact text block
    lines = []
    for r in rows:
        lines.append(f"User: {r['user']}")
        lines.append(f"SignalBot: {r['bot']}")
        lines.append("---")
    return "\n".join(lines)

