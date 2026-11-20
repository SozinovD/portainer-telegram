from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .portainer import PortainerClient, PortainerError
from .utils import esc, state_emoji

_LIST_BACK = [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="list")]


def endpoints_kb(endpoints: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🖥 {e.get('Name', e['Id'])}",
                callback_data=f"ep:{e['Id']}",
            )
        ]
        for e in endpoints
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def containers_kb(endpoint_id: int, containers: list[dict]) -> InlineKeyboardMarkup:
    def sort_key(c: dict) -> str:
        return (c.get("Names") or ["/?"])[0].lstrip("/").lower()

    rows = [
        [
            InlineKeyboardButton(
                text=_btn_label(c),
                callback_data=f"sel:{endpoint_id}:{c['Id'][:12]}",
            )
        ]
        for c in sorted(containers, key=sort_key)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def container_kb(endpoint_id: int, container_id: str, running: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if running:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔁 Restart", callback_data=f"act:{endpoint_id}:{container_id}:restart"
                ),
                InlineKeyboardButton(
                    text="⏹ Stop", callback_data=f"act:{endpoint_id}:{container_id}:stop"
                ),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="▶️ Start", callback_data=f"act:{endpoint_id}:{container_id}:start"
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📜 Логи", callback_data=f"log:{endpoint_id}:{container_id}"
            ),
            InlineKeyboardButton(
                text="📊 Stats", callback_data=f"stat:{endpoint_id}:{container_id}"
            ),
        ]
    )
    rows.append(_LIST_BACK.copy())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn_label(c: dict) -> str:
    name = (c.get("Names") or ["/?"])[0].lstrip("/")
    state = c.get("State", "")
    label = f"{state_emoji(state)} {name} — {c.get('Status', state)}"
    return label[:64]


def _ep_name(endpoints: list[dict], endpoint_id: int) -> str:
    for e in endpoints:
        if e["Id"] == endpoint_id:
            return e.get("Name", str(endpoint_id))
    return str(endpoint_id)


async def render_endpoints(portainer: PortainerClient) -> tuple[str, InlineKeyboardMarkup]:
    endpoints = await portainer.endpoints()
    if not endpoints:
        raise PortainerError("В Portainer не найдено ни одного endpoint")
    return "🖥 Выберите окружение (endpoint):", endpoints_kb(endpoints)


async def render_containers(
    portainer: PortainerClient, endpoint_id: int, endpoint_name: str | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    containers = await portainer.containers(endpoint_id)
    if not containers:
        return (
            f"🐳 Контейнеры — {esc(endpoint_name or str(endpoint_id))}: пусто",
            InlineKeyboardMarkup(inline_keyboard=[_LIST_BACK.copy()]),
        )
    lines = [f"🐳 <b>Контейнеры</b> — {esc(endpoint_name or str(endpoint_id))}", ""]
    for c in sorted(containers, key=lambda x: (x.get("Names") or ["/?"])[0].lstrip("/").lower()):
        name = (c.get("Names") or ["/?"])[0].lstrip("/")
        line = f"{state_emoji(c.get('State', ''))} <code>{esc(name)}</code> — {esc(c.get('Status', ''))}"
        lines.append(line[:200])
    return "\n".join(lines), containers_kb(endpoint_id, containers)
