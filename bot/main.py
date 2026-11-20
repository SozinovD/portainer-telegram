from __future__ import annotations

import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, CallbackQuery, Message

from .config import Config
from .handlers import router
from .portainer import PortainerClient

log = logging.getLogger("portainer-telegram")


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_chat_ids: tuple[int, ...]) -> None:
        self.allowed = allowed_chat_ids

    async def __call__(self, handler, event, data):
        chat_id: int | None = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id
        if self.allowed and chat_id not in self.allowed:
            log.warning("Access denied for chat %s", chat_id)
            return
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    if not config.allowed_chat_ids:
        log.warning("ALLOWED_CHAT_IDS is empty — bot is visible to everyone!")

    portainer = PortainerClient(config.portainer_url, config.portainer_api_key)

    bot = Bot(config.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands(
        [
            BotCommand(command="ps", description="Список контейнеров"),
            BotCommand(command="logs", description="Логи контейнера"),
            BotCommand(command="up", description="Запустить контейнер"),
            BotCommand(command="down", description="Остановить контейнер"),
            BotCommand(command="restart", description="Перезапустить контейнер"),
            BotCommand(command="help", description="Помощь"),
        ]
    )

    dp = Dispatcher()
    dp["portainer"] = portainer
    dp.message.middleware(AccessMiddleware(config.allowed_chat_ids))
    dp.callback_query.middleware(AccessMiddleware(config.allowed_chat_ids))
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await portainer.close()


if __name__ == "__main__":
    asyncio.run(main())
