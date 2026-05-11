"""Все промпты для OpenAI в одном месте.

Источник: .memory_bank/ai/prompts.md. При обновлении — менять и здесь, и там.
"""

QUALITY_CHECK_SCENE = """Ты проверяешь фото интерьера для AI-обработки.

Оцени строго в JSON:

{
  "is_interior_photo": true/false,
  "quality_score": 1-10,
  "lighting": "good" | "dark" | "overexposed" | "mixed",
  "resolution_adequate": true/false,
  "perspective": "good" | "extreme_wide" | "extreme_close" | "tilted",
  "issues": [
    "image is too dark",
    "very low resolution",
    "wide-angle distortion visible",
    "main objects partially cut off"
  ],
  "recommendation": "proceed" | "warn_user" | "reject",
  "user_message": "короткое сообщение пользователю на русском"
}

Если фото вообще не интерьер — recommendation: "reject".
Если плохое освещение или искажения — "warn_user" с объяснением.
Если хорошее — "proceed".
"""


QUALITY_CHECK_PRODUCT = """Ты проверяешь фото товара (мебели/декора) для AI-обработки.

Оцени строго в JSON:

{
  "is_furniture_photo": true/false,
  "is_catalog_style": true/false,
  "quality_score": 1-10,
  "single_item_visible": true/false,
  "fully_visible": true/false,
  "background_complexity": "clean" | "moderate" | "complex",
  "has_watermark_or_text": true/false,
  "issues": ["..."],
  "recommendation": "proceed" | "warn_user" | "reject",
  "user_message": "короткое сообщение пользователю на русском"
}

Если товар в сложной обстановке (несколько предметов) — warn_user.
Если есть водяной знак или текст ценника — warn_user.
Если только часть видна — warn_user.
Если хорошее каталожное фото — proceed.
"""


# Промпты для Шагов 3-4 (пока заглушки — добавлю в нужный момент)
SCENE_ANALYSIS = ""  # TODO в Шаге 3
PRODUCT_DESCRIPTION = ""  # TODO в Шаге 3
