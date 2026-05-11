"""Подготовка картинок перед отправкой в AI API.

Ресайз до 1280 пикселей по большей стороне + сохранение как JPEG. Экономит
трафик и стоимость vision-запросов.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_DIMENSION = 1280
JPEG_QUALITY = 90


def preprocess_image(image_bytes: bytes) -> bytes:
    """Открыть картинку, повернуть по EXIF, ресайз до 1280 по большей стороне,
    вернуть JPEG bytes."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Учитываем EXIF orientation (часто на телефоне)
        img = ImageOps.exif_transpose(img)

        # RGBA / palette → RGB (JPEG не поддерживает прозрачность)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Ресайз только если больше MAX_DIMENSION
        w, h = img.size
        max_side = max(w, h)
        if max_side > MAX_DIMENSION:
            scale = MAX_DIMENSION / max_side
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()
