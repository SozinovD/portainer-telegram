from __future__ import annotations

import html

_STATE_EMOJI = {
    "running": "🟢",
    "paused": "🟡",
    "restarting": "🔁",
    "exited": "🔴",
    "dead": "💀",
    "created": "⚪",
}


def state_emoji(state: str) -> str:
    return _STATE_EMOJI.get(state, "❔")


def esc(value: str) -> str:
    return html.escape(value, quote=False)


def fmt_bytes(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} PiB"


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return "…" + text[-limit:]
