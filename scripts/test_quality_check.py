"""Локальный тест quality_check.

Использование:
    python scripts/test_quality_check.py path/to/scene.jpg --kind scene
    python scripts/test_quality_check.py path/to/product.jpg --kind product

Берёт картинку, заливает на 0x0.st, прогоняет через quality_check, печатает JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Чтобы импорты работали из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from ai.preprocessing import preprocess_image
from ai.quality_check import check_product_quality, check_scene_quality
from utils.storage import upload_to_temp_storage


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Путь к картинке")
    parser.add_argument(
        "--kind",
        choices=["scene", "product"],
        default="scene",
        help="Что проверяем: scene (комната) или product (товар)",
    )
    args = parser.parse_args()

    if not args.image.exists():
        print(f"Файл не найден: {args.image}")
        sys.exit(1)

    print(f"[1/3] Читаю и сжимаю {args.image.name}...")
    image_bytes = args.image.read_bytes()
    processed = preprocess_image(image_bytes)
    print(f"      Размер до: {len(image_bytes)} байт, после: {len(processed)} байт")

    print("[2/3] Загружаю на временный хостинг...")
    url = await upload_to_temp_storage(processed, filename=args.image.name)
    print(f"      URL: {url}")

    print(f"[3/3] Проверка качества ({args.kind}) через OpenAI...")
    checker = check_scene_quality if args.kind == "scene" else check_product_quality
    result = await checker(url)

    print()
    print("=== Результат ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()
    asyncio.run(main())
