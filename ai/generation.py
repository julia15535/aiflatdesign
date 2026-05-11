"""Stage 3: Генерация финального фото через OpenAI gpt-image-2.

Один вызов /v1/images/edits с двумя input-картинками:
- Фото комнаты (первая в массиве — основная для редактирования)
- Фото товара (вторая — reference для сохранения визуала)

В промпте просим убрать `to_remove` и поставить `to_add` с сохранением визуальной
идентичности товара (input_fidelity="high").

Подробнее: .memory_bank/ai/generation.md
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Final

import httpx
from openai import APIError, AsyncOpenAI
from PIL import Image

from ai.prompts import GENERATION

logger = logging.getLogger(__name__)

IMAGE_MODEL: Final[str] = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
IMAGE_QUALITY: Final[str] = os.environ.get("OPENAI_IMAGE_QUALITY", "medium")
IMAGE_INPUT_FIDELITY: Final[str] = os.environ.get("OPENAI_IMAGE_INPUT_FIDELITY", "high")
GENERATION_TIMEOUT_SEC: Final[float] = 120.0
DOWNLOAD_TIMEOUT_SEC: Final[float] = 30.0

# Цены на gpt-image-2 (примерно, для логирования; точные считаются по токенам)
# https://developers.openai.com/api/docs/pricing
_PRICES_PER_IMAGE: dict[str, dict[str, float]] = {
    "gpt-image-2": {"low": 0.006, "medium": 0.024, "high": 0.12},
    "gpt-image-1.5": {"low": 0.009, "medium": 0.034, "high": 0.133},
    "gpt-image-1": {"low": 0.011, "medium": 0.042, "high": 0.167},
}


def _build_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=GENERATION_TIMEOUT_SEC)


async def _download_image(url: str) -> bytes:
    """Скачать картинку по URL (с 0x0.st или catbox.moe)."""
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_SEC, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _detect_output_size(image_bytes: bytes) -> str:
    """Выбрать размер вывода по ориентации фото комнаты.

    OpenAI поддерживает только фиксированные: 1024x1024, 1536x1024, 1024x1536.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
    except Exception:
        return "1024x1024"
    ratio = w / h if h > 0 else 1.0
    if ratio >= 1.25:
        return "1536x1024"  # горизонтальное
    if ratio <= 0.8:
        return "1024x1536"  # вертикальное
    return "1024x1024"  # квадратное / близко к нему


def _estimate_cost(model: str, quality: str) -> float:
    return _PRICES_PER_IMAGE.get(model, {}).get(quality, 0.024)


async def generate_room_with_product(
    scene_url: str,
    product_url: str,
    to_remove_en: str,
    to_remove_ru: str,
    to_add_en: str,
    to_add_ru: str,
    ceiling_cm: int,
    room_description: str,
    product_dims_cm: tuple[float, float, float],
) -> dict:
    """Сгенерировать фото комнаты со вписанным товаром через gpt-image-2.

    Returns:
        dict:
            success: bool
            image_bytes: bytes | None     — финальное PNG (если success)
            error: str | None             — описание ошибки
            error_type: str | None        — категория ('api', 'network', 'unsupported', 'unknown')
            cost_estimate_usd: float
            duration_sec: int
            model: str
            quality: str
            size: str
    """
    start = time.time()
    result: dict = {
        "success": False,
        "image_bytes": None,
        "error": None,
        "error_type": None,
        "cost_estimate_usd": 0.0,
        "duration_sec": 0,
        "model": IMAGE_MODEL,
        "quality": IMAGE_QUALITY,
        "size": None,
    }

    # 1. Скачиваем обе картинки с 0x0.st (gpt-image edit не принимает URL — только файлы)
    try:
        scene_bytes = await _download_image(scene_url)
        product_bytes = await _download_image(product_url)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"Не удалось скачать картинки: {e}"
        result["error_type"] = "network"
        result["duration_sec"] = int(time.time() - start)
        logger.exception("Download failed: %s", e)
        return result

    # 2. Подбираем размер выхода по ориентации сцены
    size = _detect_output_size(scene_bytes)
    result["size"] = size

    prompt = GENERATION.format(
        to_remove_en=to_remove_en,
        to_remove_ru=to_remove_ru,
        to_add_en=to_add_en,
        to_add_ru=to_add_ru,
        ceiling_cm=ceiling_cm,
        room_description=room_description or "не указано",
        prod_w=int(product_dims_cm[0]),
        prod_d=int(product_dims_cm[1]),
        prod_h=int(product_dims_cm[2]),
    )

    # 3. Вызов /v1/images/edits через gpt-image-2
    client = _build_client()

    # SDK ожидает FileTypes (bytes / tuple(filename, bytes, content_type) / IO).
    # Используем tuple — самый надёжный формат.
    images_payload = [
        ("scene.png", scene_bytes, "image/png"),
        ("product.png", product_bytes, "image/png"),
    ]

    try:
        response = await client.images.edit(
            model=IMAGE_MODEL,
            image=images_payload,
            prompt=prompt,
            input_fidelity=IMAGE_INPUT_FIDELITY,
            quality=IMAGE_QUALITY,
            size=size,
            n=1,
        )
    except APIError as e:
        err_msg = str(e)
        # Если модель недоступна — попробуем gpt-image-1.5
        if "model" in err_msg.lower() and ("not found" in err_msg.lower() or "does not exist" in err_msg.lower()):
            logger.warning("Model %s недоступна, пробую gpt-image-1.5: %s", IMAGE_MODEL, e)
            try:
                response = await client.images.edit(
                    model="gpt-image-1.5",
                    image=images_payload,
                    prompt=prompt,
                    input_fidelity=IMAGE_INPUT_FIDELITY,
                    quality=IMAGE_QUALITY,
                    size=size,
                    n=1,
                )
                result["model"] = "gpt-image-1.5"
            except APIError as e2:
                result["error"] = f"OpenAI API: {e2}"
                result["error_type"] = "api"
                result["duration_sec"] = int(time.time() - start)
                logger.exception("Fallback to gpt-image-1.5 также упал: %s", e2)
                return result
        else:
            result["error"] = f"OpenAI API: {e}"
            result["error_type"] = "api"
            result["duration_sec"] = int(time.time() - start)
            logger.exception("OpenAI API error: %s", e)
            return result
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
        result["error_type"] = "unknown"
        result["duration_sec"] = int(time.time() - start)
        logger.exception("Unexpected error in generation: %s", e)
        return result

    # 4. Извлечь картинку из ответа
    if not response.data:
        result["error"] = "OpenAI вернул пустой data"
        result["error_type"] = "api"
        result["duration_sec"] = int(time.time() - start)
        return result

    item = response.data[0]
    image_bytes: bytes | None = None

    # gpt-image-2 обычно возвращает b64_json, но может и url
    if getattr(item, "b64_json", None):
        try:
            image_bytes = base64.b64decode(item.b64_json)
        except Exception as e:  # noqa: BLE001
            result["error"] = f"Не удалось декодировать b64: {e}"
            result["error_type"] = "api"
            result["duration_sec"] = int(time.time() - start)
            return result
    elif getattr(item, "url", None):
        try:
            image_bytes = await _download_image(item.url)
        except Exception as e:  # noqa: BLE001
            result["error"] = f"Не удалось скачать результат с URL: {e}"
            result["error_type"] = "network"
            result["duration_sec"] = int(time.time() - start)
            return result
    else:
        result["error"] = "В ответе нет ни b64_json, ни url"
        result["error_type"] = "api"
        result["duration_sec"] = int(time.time() - start)
        return result

    result["success"] = True
    result["image_bytes"] = image_bytes
    result["cost_estimate_usd"] = _estimate_cost(result["model"], IMAGE_QUALITY)
    result["duration_sec"] = int(time.time() - start)

    logger.info(
        "Generation OK: model=%s, quality=%s, size=%s, %d сек, ~$%.3f",
        result["model"], IMAGE_QUALITY, size,
        result["duration_sec"], result["cost_estimate_usd"],
    )
    return result
