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


SLOT_ESTIMATION = """Ты эксперт по интерьерам. По фотографии комнаты оцени размеры свободного места, куда обычно ставят {target_en} ({target_ru}).

Дано:
- Фотография комнаты (возможно видна только часть)
- Высота потолка: {ceiling_cm} см
- Описание от пользователя: "{room_description}"

Подумай пошагово:
1. Какие в кадре референсы масштаба? Возможные варианты: дверь (200-210см высота), межкомнатная дверь (190-200см), окно (стандартное 140-160см высота), подоконник (75-90см от пола), радиатор (50-60см), плинтус (8-15см), розетка (~30см от пола), стандартный стул (45см сиденье, 90см спинка).
2. С учётом высоты потолка ({ceiling_cm} см) определи примерный масштаб — сколько сантиметров реальности приходится на видимую вертикаль.
3. Где обычно ставят {target_en} в такой комнате? (диван — вдоль стены или в углу, обеденный стол — у окна или в эркере, кровать — у длинной стены, и т.п.)
4. Если место под {target_en} в кадре — оцени его реальный размер в сантиметрах. Если место не в кадре — попробуй оценить по описанию и пропорциям.

Верни СТРОГО JSON следующего формата:
{{
  "scale_references": ["конкретные объекты в кадре с их примерными размерами в см"],
  "estimated_slot": {{
    "width_cm": 250,
    "depth_cm": 90,
    "height_cm": 90
  }},
  "confidence": "low | medium | high",
  "reasoning": "1-2 коротких предложения на русском, почему такие цифры",
  "warnings": ["комната видна частично", "потолок мог быть указан неточно", ...],
  "is_target_appropriate_for_room": true,
  "appropriate_explanation": "пустая строка если всё OK или объяснение почему предмет нетипичен"
}}

Если фото настолько плохое что оценка невозможна — confidence=low и в warnings подробно объясни.

ВАЖНО про размеры:
- width_cm — длина (более длинная сторона по горизонтали)
- depth_cm — глубина (от стены или ширина по другой горизонтальной оси)
- height_cm — высота (вертикаль)
- Для дивана типично width=180-280, depth=85-110, height=80-95
- Для обеденного стола width=120-200, depth=80-100, height=72-78
- Для кровати двуспальной width=140-200, depth=190-220, height=40-50 (без матраца)

ВАЖНО про confidence:
- high: видны 3+ референса масштаба, потолок похож на правду, описание непротиворечиво
- medium: 1-2 референса, есть сомнения
- low: фото нечёткое, мало референсов, или потолок выглядит подозрительно (например указано 200см но видна дверь высотой как 2 потолка)
"""


GENERATION = """You are editing the first image (a room photo) to perform a furniture replacement.

REMOVE: {to_remove_en} ({to_remove_ru}) currently in the room.
ADD: a {to_add_en} ({to_add_ru}) that looks EXACTLY like the second image (reference product).

Real-world context (use as scale reference):
- Ceiling height: {ceiling_cm} cm
- Room description: "{room_description}"
- Product dimensions: {prod_w} x {prod_d} x {prod_h} cm

CRITICAL VISUAL IDENTITY REQUIREMENTS:
- The {to_add_en} MUST look exactly like the reference product (second image).
- Preserve: exact color, exact pattern/texture, exact shape, exact materials, exact proportions, design details (legs, handles, finish, fabric).
- DO NOT reinterpret, simplify, or change the product's appearance in any way.
- The added furniture should look like the SAME piece from the reference, not a similar one.

SCENE INTEGRITY REQUIREMENTS:
- Keep the room's original walls, floor, ceiling, windows, doors, lighting, and perspective unchanged.
- Keep all other furniture (not being replaced) unchanged in position and appearance.
- The new product should have natural shadows, reflections, and perspective matching the room's existing lighting.
- Photorealistic output. No text, watermark, or labels in the result.
- The result should look like a real photograph of the same room.

If the removed item is not clearly visible in the room (mentioned for context but not present in the photo), still add the new product in the most natural location.
"""


# Промпты для будущего расширения (Шаг 4 если потребуется)
SCENE_ANALYSIS = ""  # TODO если решим вернуть GroundedSAM
PRODUCT_DESCRIPTION = ""  # TODO если решим вернуть FLUX Fill Pro
