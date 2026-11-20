from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from .keyboards import container_kb, render_containers, render_endpoints
from .portainer import PortainerClient, PortainerError
from .utils import esc, fmt_bytes, state_emoji, truncate

router = Router(name="main")

MAX_LEN = 3800

HELP = (
    "🐳 <b>Portainer Telegram Bot</b> — мини-UI для управления Docker-контейнерами.\n\n"
    "Команды:\n"
    "/ps — список контейнеров\n"
    "/logs &lt;имя&gt; [n] — последние n строк логов (по умолчанию 50)\n"
    "/up &lt;имя&gt; — запустить контейнер\n"
    "/down &lt;имя&gt; — остановить контейнер\n"
    "/restart &lt;имя&gt; — перезапустить контейнер\n\n"
    "Или отправьте /ps и управляйте через кнопки."
)

ACTION_LABELS = {"start": "Запущен", "stop": "Остановлен", "restart": "Перезапущен"}


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("ps", "containers"))
async def cmd_containers(message: Message, portainer: PortainerClient) -> None:
    try:
        text, kb = await _render_list(portainer)
    except PortainerError as e:
        await message.answer(f"⚠️ {esc(str(e))}")
        return
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "list")
async def cb_list(callback: CallbackQuery, portainer: PortainerClient) -> None:
    try:
        text, kb = await _render_list(portainer)
    except PortainerError as e:
        await callback.answer(str(e)[:190], show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


async def _render_list(portainer: PortainerClient):
    endpoints = await portainer.endpoints()
    if not endpoints:
        raise PortainerError("В Portainer не найдено ни одного endpoint")
    if len(endpoints) == 1:
        ep = endpoints[0]
        return await render_containers(portainer, ep["Id"], ep.get("Name"))
    return await render_endpoints(portainer)


@router.callback_query(F.data.startswith("ep:"))
async def cb_endpoint(callback: CallbackQuery, portainer: PortainerClient) -> None:
    endpoint_id = int(callback.data.split(":", 1)[1])  # type: ignore[union-attr]
    try:
        text, kb = await render_containers(portainer, endpoint_id)
    except PortainerError as e:
        await callback.answer(str(e)[:190], show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("sel:"))
async def cb_select(callback: CallbackQuery, portainer: PortainerClient) -> None:
    _, endpoint_id, container_id = callback.data.split(":", 2)  # type: ignore[union-attr]
    try:
        await _edit_container_menu(callback, portainer, int(endpoint_id), container_id)
    except PortainerError as e:
        await callback.answer(str(e)[:190], show_alert=True)
        return
    await callback.answer()


async def _edit_container_menu(
    callback: CallbackQuery, portainer: PortainerClient, endpoint_id: int, container_id: str
) -> None:
    info = await portainer.inspect(endpoint_id, container_id)
    name = info.get("Name", "?").lstrip("/")
    state = info.get("State", {}).get("Status", "unknown")
    image = info.get("Config", {}).get("Image", "?")
    restarts = info.get("RestartCount", 0)

    text = (
        f"{state_emoji(state)} <b>{esc(name)}</b>\n\n"
        f"Состояние: <code>{esc(state)}</code>\n"
        f"Образ: <code>{esc(image)}</code>\n"
        f"Перезапусков: {restarts}"
    )
    kb = container_kb(endpoint_id, container_id, running=state == "running")
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("act:"))
async def cb_action(callback: CallbackQuery, portainer: PortainerClient) -> None:
    _, endpoint_id, container_id, action = callback.data.split(":", 3)  # type: ignore[union-attr]
    try:
        await portainer.action(int(endpoint_id), container_id, action)
    except PortainerError as e:
        await callback.answer(str(e)[:190], show_alert=True)
        return
    await callback.answer(f"✅ {ACTION_LABELS.get(action, action)}")
    try:
        await _edit_container_menu(callback, portainer, int(endpoint_id), container_id)
    except PortainerError:
        pass


@router.callback_query(F.data.startswith("log:"))
async def cb_logs(callback: CallbackQuery, portainer: PortainerClient) -> None:
    _, endpoint_id, container_id = callback.data.split(":", 2)  # type: ignore[union-attr]
    await callback.answer("Загружаю логи…")
    try:
        text = await _logs_text(portainer, int(endpoint_id), container_id, 50)
    except PortainerError as e:
        await callback.message.answer(f"⚠️ {esc(str(e))}")  # type: ignore[union-attr]
        return
    await callback.message.answer(text)  # type: ignore[union-attr]


async def _logs_text(
    portainer: PortainerClient, endpoint_id: int, container_id: str, tail: int
) -> str:
    info = await portainer.inspect(endpoint_id, container_id)
    name = info.get("Name", "?").lstrip("/")
    logs = await portainer.logs(endpoint_id, container_id, tail=tail)
    body = logs.strip() or "(пусто)"
    return truncate(
        f"📜 Логи <b>{esc(name)}</b> (последние {tail} строк):\n<pre>{esc(body)}</pre>",
        MAX_LEN,
    )


@router.callback_query(F.data.startswith("stat:"))
async def cb_stats(callback: CallbackQuery, portainer: PortainerClient) -> None:
    _, endpoint_id, container_id = callback.data.split(":", 2)  # type: ignore[union-attr]
    await callback.answer("Собираю статистику…")
    try:
        text = await _stats_text(portainer, int(endpoint_id), container_id)
    except PortainerError as e:
        await callback.message.answer(f"⚠️ {esc(str(e))}")  # type: ignore[union-attr]
        return
    await callback.message.answer(text)  # type: ignore[union-attr]


async def _stats_text(portainer: PortainerClient, endpoint_id: int, container_id: str) -> str:
    info = await portainer.inspect(endpoint_id, container_id)
    name = info.get("Name", "?").lstrip("/")
    s = await portainer.stats(endpoint_id, container_id)

    cpu = s.get("cpu_stats", {})
    precpu = s.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get(
        "cpu_usage", {}
    ).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    online = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or [1])
    cpu_pct = (cpu_delta / system_delta) * online * 100 if system_delta > 0 else 0.0

    mem = s.get("memory_stats", {})
    mem_usage = mem.get("usage", 0)
    mem_limit = mem.get("limit", 0)
    mem_pct = mem_usage / mem_limit * 100 if mem_limit else 0.0

    net_down = net_up = 0
    for iface in s.get("networks", {}).values():
        net_down += iface.get("rx_bytes", 0)
        net_up += iface.get("tx_bytes", 0)

    blk_read = blk_write = 0
    for item in (s.get("blkio_stats", {}).get("io_service_bytes_recursive") or []):
        if item.get("op") == "read":
            blk_read += item.get("value", 0)
        elif item.get("op") == "write":
            blk_write += item.get("value", 0)

    return (
        f"📊 <b>{esc(name)}</b>\n\n"
        f"CPU: <b>{cpu_pct:.2f}%</b> ({online} ядер)\n"
        f"RAM: <b>{fmt_bytes(mem_usage)}</b> / {fmt_bytes(mem_limit)} ({mem_pct:.1f}%)\n"
        f"NET: ↓ {fmt_bytes(net_down)}  ↑ {fmt_bytes(net_up)}\n"
        f"DISK: R {fmt_bytes(blk_read)} / W {fmt_bytes(blk_write)}"
    )


# --- Команды с поиском контейнера по имени ---


async def _find_container(
    portainer: PortainerClient, query: str
) -> tuple[int, dict] | None:
    query = query.lower().lstrip("/")
    exact: tuple[int, dict] | None = None
    partial: tuple[int, dict] | None = None
    for ep in await portainer.endpoints():
        for c in await portainer.containers(ep["Id"]):
            name = (c.get("Names") or ["/?"])[0].lstrip("/").lower()
            if name == query or c["Id"].startswith(query):
                return ep["Id"], c
            if query in name and exact is None:
                exact = (ep["Id"], c)
            elif query in c["Id"] and partial is None:
                partial = (ep["Id"], c)
    return exact or partial


@router.message(Command("logs"))
async def cmd_logs(message: Message, command: CommandObject, portainer: PortainerClient) -> None:
    parts = (command.args or "").split()
    if not parts:
        await message.answer("Использование: /logs &lt;имя_контейнера&gt; [строк]")
        return
    query, tail = parts[0], 50
    if len(parts) > 1 and parts[1].isdigit():
        tail = min(int(parts[1]), 500)
    try:
        found = await _find_container(portainer, query)
        if not found:
            await message.answer(f"⚠️ Контейнер «{esc(query)}» не найден")
            return
        endpoint_id, container = found
        text = await _logs_text(portainer, endpoint_id, container["Id"], tail)
    except PortainerError as e:
        await message.answer(f"⚠️ {esc(str(e))}")
        return
    await message.answer(text)


@router.message(Command("up", "down", "restart"))
async def cmd_action(message: Message, command: CommandObject, portainer: PortainerClient) -> None:
    action = {"up": "start", "down": "stop", "restart": "restart"}[command.command]
    query = (command.args or "").strip()
    if not query:
        await message.answer(f"Использование: /{command.command} &lt;имя_контейнера&gt;")
        return
    try:
        found = await _find_container(portainer, query)
        if not found:
            await message.answer(f"⚠️ Контейнер «{esc(query)}» не найден")
            return
        endpoint_id, container = found
        name = (container.get("Names") or ["?"])[0].lstrip("/")
        await portainer.action(endpoint_id, container["Id"], action)
    except PortainerError as e:
        await message.answer(f"⚠️ {esc(str(e))}")
        return
    await message.answer(f"✅ {ACTION_LABELS[action]}: <code>{esc(name)}</code>")
