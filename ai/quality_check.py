"""Stage 0: Проверка качества фото через OpenAI vision.

Возвращает словарь с recommendation: proceed / warn_user / reject.

Подробно: .memory_bank/ai/quality_check.md
"""

from __future__ import annotations

import json
import logging
import os
from typing import Final

from openai import APIError, AsyncOpenAI

from ai.prompts import QUALITY_CHECK_PRODUCT, QUALITY_CHECK_SCENE

logger = logging.getLogger(__name__)

QUALITY_MODEL: Final[str] = os.environ.get("OPENAI_QUALITY_CHECK_MODEL", "gpt-5.4-mini")
MAX_TOKENS: Final[int] = 600
TIMEOUT_SEC: Final[float] = 30.0


def _build_client() -> AsyncOpenAI:
    """Клиент OpenAI с настройкой через прокси если указан OPENAI_BASE_URL."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or None  # пустая строка → None
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SEC)


def _fallback_proceed(reason: str) -> dict:
    """Если OpenAI упал — не блокируем пользователя, пропускаем дальше."""
    logger.warning("Quality check fallback на proceed: %s", reason)
    return {
        "recommendation": "proceed",
        "user_message": "",
        "issues": [f"qc_unavailable: {reason}"],
        "quality_score": None,
        "_fallback": True,
    }


async def _run_quality_check(image_url: str, prompt: str, *, label: str) -> dict:
    """Общая логика для проверки сцены и товара."""
    try:
        client = _build_client()
        response = await client.chat.completions.create(
            model=QUALITY_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "low",  # 512×512 хватает для QC
                            },
                        },
                    ],
                }
            ],
            max_tokens=MAX_TOKENS,
        )
    except APIError as e:
        return _fallback_proceed(f"OpenAI API: {e}")
    except Exception as e:  # noqa: BLE001
        return _fallback_proceed(f"unexpected: {type(e).__name__}: {e}")

    content = response.choices[0].message.content or ""
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        return _fallback_proceed(f"невалидный JSON: {e}")

    if "recommendation" not in result:
        return _fallback_proceed("в ответе нет поля recommendation")

    logger.info(
        "QC %s → %s (score=%s, issues=%s)",
        label,
        result.get("recommendation"),
        result.get("quality_score"),
        result.get("issues"),
    )
    return result


async def check_scene_quality(image_url: str) -> dict:
    """Проверка качества фото интерьера."""
    return await _run_quality_check(image_url, QUALITY_CHECK_SCENE, label="scene")


async def check_product_quality(image_url: str) -> dict:
    """Проверка качества фото товара (мебели/декора)."""
    return await _run_quality_check(image_url, QUALITY_CHECK_PRODUCT, label="product")
