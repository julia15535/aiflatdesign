"""Загрузка картинки на бесплатный временный хостинг.

Замысел: OpenAI и Replicate принимают картинки по URL. Мы кладём картинку на
0x0.st (анонимный, ~1 час жизни, без API ключа), получаем URL, передаём дальше.

Если 0x0.st недоступен — пытаемся через catbox.moe (тоже без ключа).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

logger = logging.getLogger(__name__)

ZERO_X_ZERO_URL: Final[str] = "https://0x0.st"
CATBOX_URL: Final[str] = "https://catbox.moe/user/api.php"

# 0x0.st требует osm user agent (иначе 403)
USER_AGENT: Final[str] = "aiflatdesigner-bot/0.1 (+https://github.com/julia15535/aiflatdesign)"

UPLOAD_TIMEOUT_SEC: Final[float] = 30.0


async def upload_to_temp_storage(image_bytes: bytes, filename: str = "image.jpg") -> str:
    """Загрузить картинку и вернуть публичный URL. Пытается 0x0.st, потом catbox.moe.

    Raises:
        RuntimeError: если оба сервиса упали.
    """
    last_error: Exception | None = None

    for attempt_name, uploader in (("0x0.st", _upload_to_0x0), ("catbox.moe", _upload_to_catbox)):
        try:
            url = await uploader(image_bytes, filename)
            logger.info("Картинка загружена через %s: %s", attempt_name, url)
            return url
        except Exception as e:  # noqa: BLE001 — нам нужно поймать любую ошибку и попробовать запасной
            logger.warning("Не удалось через %s: %s", attempt_name, e)
            last_error = e

    raise RuntimeError(f"Все сервисы загрузки картинок недоступны. Последняя ошибка: {last_error}")


async def _upload_to_0x0(image_bytes: bytes, filename: str) -> str:
    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT_SEC) as client:
        resp = await client.post(
            ZERO_X_ZERO_URL,
            files={"file": (filename, image_bytes, "image/jpeg")},
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise RuntimeError(f"0x0.st вернул не URL: {url!r}")
        return url


async def _upload_to_catbox(image_bytes: bytes, filename: str) -> str:
    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT_SEC) as client:
        resp = await client.post(
            CATBOX_URL,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (filename, image_bytes, "image/jpeg")},
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise RuntimeError(f"catbox.moe вернул не URL: {url!r}")
        return url


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python utils/storage.py <image_path>")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        data = f.read()
    url = asyncio.run(upload_to_temp_storage(data, filename=sys.argv[1].rsplit("/", 1)[-1]))
    print(f"URL: {url}")
