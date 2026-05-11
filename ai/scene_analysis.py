"""Stage 1 (pre-flight, упрощённая версия): оценка размеров места под объект
по фото комнаты через OpenAI vision.

В полной реализации Шага 3 здесь же будет вызов GroundedSAM для точной маски.
Пока — только текстовая оценка от ИИ + дефолты при ошибках.

Подробнее: .memory_bank/ai/scene_analysis.md
"""

from __future__ import annotations

import json
import logging
import os
from typing import Final

from openai import APIError, AsyncOpenAI

from ai.prompts import SLOT_AFTER_REMOVAL, SLOT_ESTIMATION

logger = logging.getLogger(__name__)

VISION_MODEL: Final[str] = os.environ.get("OPENAI_VISION_MODEL", "gpt-5.4-mini")
MAX_TOKENS: Final[int] = 1500
TIMEOUT_SEC: Final[float] = 45.0

# Дефолтные размеры мест по типу объекта (см) — используем если ИИ упал
_DEFAULT_SLOTS: dict[str, tuple[int, int, int]] = {
    "sofa": (220, 95, 90),
    "sectional sofa": (280, 220, 95),
    "armchair": (90, 90, 90),
    "ottoman": (60, 60, 45),
    "bench": (130, 45, 50),
    "table": (130, 80, 75),
    "dining table": (140, 90, 76),
    "coffee table": (110, 60, 45),
    "desk": (130, 60, 75),
    "console table": (120, 35, 80),
    "bed": (160, 200, 50),
    "double bed": (180, 200, 50),
    "single bed": (100, 200, 50),
    "nightstand": (50, 40, 55),
    "wardrobe": (200, 60, 220),
    "dresser": (120, 50, 90),
    "shelf unit": (90, 40, 200),
    "wall shelf": (90, 25, 30),
    "bookshelf": (90, 35, 200),
    "chair": (45, 50, 90),
    "bar stool": (40, 40, 90),
    "office chair": (60, 60, 110),
    "lamp": (35, 35, 60),
    "table lamp": (30, 30, 50),
    "floor lamp": (35, 35, 160),
    "chandelier": (60, 60, 70),
    "ceiling light": (40, 40, 25),
    "rug": (200, 150, 2),
    "small rug": (120, 80, 2),
    "mirror": (60, 5, 100),
    "painting": (80, 5, 60),
    "poster": (60, 1, 90),
    "vase": (25, 25, 40),
    "plant": (40, 40, 100),
    "TV": (120, 8, 70),
    "TV stand": (160, 45, 50),
}


def _build_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SEC)


def _fallback_estimate(target_en: str, reason: str) -> dict:
    """Если ИИ упал — используем дефолты по типу объекта."""
    w, d, h = _DEFAULT_SLOTS.get(target_en, (150, 80, 80))
    logger.warning("Slot estimation fallback: %s. target=%s, default=%sx%sx%s", reason, target_en, w, d, h)
    return {
        "scale_references": [],
        "estimated_slot": {"width_cm": w, "depth_cm": d, "height_cm": h},
        "confidence": "low",
        "reasoning": f"Не удалось проанализировать фото ({reason}). Использую средние дефолты для {target_en}.",
        "warnings": [f"ai_unavailable: {reason}"],
        "is_target_appropriate_for_room": True,
        "appropriate_explanation": "",
        "_fallback": True,
    }


async def estimate_post_removal_slot(
    scene_url: str,
    to_remove: str,
    to_add_with_placement: str,
    ceiling_cm: int,
    room_description: str,
) -> dict:
    """Vision-оценка размеров свободного места ПОСЛЕ удаления `to_remove`.

    Возвращает dict:
        free_area_after_removal: {width_cm, depth_cm, height_cm}
        confidence: "low|medium|high"
        reasoning: str (на русском)
        warnings: list[str]
    """
    prompt = SLOT_AFTER_REMOVAL.format(
        to_remove=to_remove,
        to_add_with_placement=to_add_with_placement or "куда угодно",
        ceiling_cm=ceiling_cm,
        room_description=room_description or "не указано",
    )

    try:
        client = _build_client()
        response = await client.chat.completions.create(
            model=VISION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": scene_url, "detail": "high"},
                        },
                    ],
                }
            ],
            max_tokens=MAX_TOKENS,
        )
    except APIError as e:
        return _post_removal_fallback(f"OpenAI API: {e}")
    except Exception as e:  # noqa: BLE001
        return _post_removal_fallback(f"unexpected: {type(e).__name__}: {e}")

    content = response.choices[0].message.content or ""
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        return _post_removal_fallback(f"невалидный JSON: {e}")

    area = result.get("free_area_after_removal")
    if not isinstance(area, dict) or not all(k in area for k in ("width_cm", "depth_cm", "height_cm")):
        return _post_removal_fallback("в ответе нет полного free_area_after_removal")

    for axis in ("width_cm", "depth_cm", "height_cm"):
        try:
            area[axis] = int(area[axis])
        except (TypeError, ValueError):
            return _post_removal_fallback(f"некорректное {axis}: {area.get(axis)!r}")
        if not (10 <= area[axis] <= 600):
            return _post_removal_fallback(f"{axis}={area[axis]} вне диапазона 10-600")

    logger.info(
        "Post-removal slot: %sx%sx%s, confidence=%s, reasoning=%s",
        area["width_cm"], area["depth_cm"], area["height_cm"],
        result.get("confidence"),
        (result.get("reasoning") or "")[:80],
    )
    return result


def _post_removal_fallback(reason: str) -> dict:
    """Дефолт когда vision упал. Берём средние «комнатные» цифры."""
    logger.warning("Post-removal slot fallback: %s", reason)
    return {
        "free_area_after_removal": {"width_cm": 200, "depth_cm": 90, "height_cm": 220},
        "confidence": "low",
        "reasoning": f"Не удалось оценить ({reason}). Беру средние цифры для жилой комнаты.",
        "warnings": [f"vision_unavailable: {reason}"],
        "_fallback": True,
    }


async def estimate_slot_dimensions(
    scene_url: str,
    target_en: str,
    target_ru: str,
    ceiling_cm: int,
    room_description: str,
) -> dict:
    """Оценить размеры свободного места под `target_en` в комнате.

    Args:
        scene_url: публичный URL фото комнаты
        target_en: английское название объекта (для промпта)
        target_ru: русское название (для подсказки ИИ в скобках)
        ceiling_cm: высота потолка в сантиметрах (масштабный референс)
        room_description: текстовое описание от пользователя

    Returns:
        dict с полями estimated_slot, confidence, reasoning, warnings и т.д.
    """
    prompt = SLOT_ESTIMATION.format(
        target_en=target_en,
        target_ru=target_ru,
        ceiling_cm=ceiling_cm,
        room_description=room_description or "не указано",
    )

    try:
        client = _build_client()
        response = await client.chat.completions.create(
            model=VISION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": scene_url,
                                "detail": "high",  # важны мелкие референсы
                            },
                        },
                    ],
                }
            ],
            max_tokens=MAX_TOKENS,
        )
    except APIError as e:
        return _fallback_estimate(target_en, f"OpenAI API: {e}")
    except Exception as e:  # noqa: BLE001
        return _fallback_estimate(target_en, f"unexpected: {type(e).__name__}: {e}")

    content = response.choices[0].message.content or ""
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        return _fallback_estimate(target_en, f"невалидный JSON: {e}")

    slot = result.get("estimated_slot")
    if not isinstance(slot, dict) or not all(k in slot for k in ("width_cm", "depth_cm", "height_cm")):
        return _fallback_estimate(target_en, "в ответе нет полного estimated_slot")

    # Sanitize: размеры должны быть в разумных границах (10см — 500см)
    for axis in ("width_cm", "depth_cm", "height_cm"):
        try:
            slot[axis] = int(slot[axis])
        except (TypeError, ValueError):
            return _fallback_estimate(target_en, f"некорректное {axis}: {slot.get(axis)!r}")
        if not (5 <= slot[axis] <= 600):
            return _fallback_estimate(target_en, f"{axis}={slot[axis]} вне диапазона 5-600")

    logger.info(
        "Slot estimation: target=%s, slot=%sx%sx%s, confidence=%s",
        target_en, slot["width_cm"], slot["depth_cm"], slot["height_cm"],
        result.get("confidence"),
    )
    return result
