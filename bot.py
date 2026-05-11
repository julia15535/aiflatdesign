"""Главный entry-point бота.

Загружает .env, инициализирует БД, поднимает aiogram, запускает polling.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db import init_db
from handlers import router

logger = logging.getLogger(__name__)


def _build_session() -> AiohttpSession | None:
    """Если задан TG_API_BASE_URL — используем зеркало Telegram API
    (для обхода блокировки api.telegram.org). Иначе — None (дефолт aiogram)."""
    base = os.environ.get("TG_API_BASE_URL", "").strip()
    if not base:
        return None
    server = TelegramAPIServer.from_base(base)
    logger.info("Telegram API через зеркало: %s", base)
    return AiohttpSession(api=server)


async def main() -> None:
    load_dotenv()

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        logger.error("TG_BOT_TOKEN не задан в окружении. Проверь .env.")
        sys.exit(1)

    init_db()

    session = _build_session()
    bot = Bot(
        token=token,
        session=session,  # type: ignore[arg-type]  # None допустим — aiogram создаст дефолт
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    me = await bot.get_me()
    logger.info("Бот запущен: @%s (id=%s)", me.username, me.id)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлен по Ctrl+C")
