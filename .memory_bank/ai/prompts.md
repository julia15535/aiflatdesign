# Промпты (единое место)

Все промпты в коде должны импортироваться из `ai/prompts.py` — никаких "магических строк" inline.

## Stage 0: Quality Check сцены

```
Ты проверяешь фото интерьера для AI-обработки.

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
```

## Stage 0: Quality Check товара

```
Ты проверяешь фото товара (мебели/декора) для AI-обработки.

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
```

## Stage 1 (упрощённый, Шаг 2.5): Slot Estimation

См. `SLOT_ESTIMATION` в `ai/prompts.py`. Промпт принимает параметры:
- `{target_en}`, `{target_ru}` — что вписываем
- `{ceiling_cm}` — высота потолка (масштабный референс)
- `{room_description}` — текстовое описание от пользователя

Промпт инструктирует ИИ:
1. Найти в кадре референсы масштаба (дверь, окно, плинтус, радиатор, розетки, стулья — с типичными размерами)
2. Определить масштаб через высоту потолка
3. Прикинуть где обычно ставят `{target_en}` в такой комнате
4. Оценить реальный размер места в см

Возвращает JSON: `estimated_slot {width_cm, depth_cm, height_cm}`, `confidence`, `reasoning`, `warnings`, `is_target_appropriate_for_room`.

В Шаге 3 этот промпт **дополнится** GroundedSAM-вызовом для точной маски.

## Stage 1: Scene Analysis

```
Проанализируй фото интерьера для AI-обработки. Верни строго JSON:

{
  "room_type": "living_room" | "bedroom" | "kitchen" | "bathroom" | "office" | "hallway" | "other",
  "perspective": "wide_angle" | "normal" | "tight",
  "lighting": "natural_daylight" | "evening" | "artificial" | "mixed",
  "style": "modern" | "scandinavian" | "classic" | "loft" | "minimalist" | "other",
  "existing_objects": ["sofa", "coffee table", "lamp"],
  "estimated_room_area_sqm": 25,
  "wall_color": "neutral_white" | "warm_grey" | "blue" | "other",
  "floor_type": "wood_light" | "wood_dark" | "tile" | "carpet" | "laminate",
  "scale_references": [
    "door visible (assumed 200cm tall)",
    "window with sill (assumed 80cm)",
    "person not visible"
  ],
  "complexity": "easy" | "medium" | "hard",
  "issues": []
}
```

## Stage 3: Product Description

```
Опиши этот предмет мебели для AI image generation prompt. Включи:
- тип
- цвет
- материал/обивку
- узор/паттерн (если есть)
- форму
- стиль ножек/основания
- особые детали

Кратко, до 60 слов, на английском, без preamble.
```

## Stage 3: Generation Prompt

Динамический, собирается из:

```
"a {target_class} that matches the reference product exactly. "
"{product_description}. "
"{style} interior style, {lighting} lighting matching the room. "
"photorealistic, sharp focus, high detail, magazine-quality interior photography. "
"the {target_class} should fit naturally into the existing room geometry."
```

## Stage 3: Negative Prompt

```
deformed, distorted, blurry, cartoon, oversaturated, plastic look,
fake, CGI, warped perspective, floating furniture, duplicated objects,
melting furniture, mismatched scale, watermark, text, logo, low quality
```

## Stage 5: Clarity Upscaler

- Prompt: `"masterpiece, best quality, photorealistic interior"`
- Negative: `"blurry, low quality, watermark, text"`

## Принципы при подгонке промптов

1. **Меняем по одному параметру за раз** — иначе непонятно что сработало.
2. **Бенчмарк до и после** — на тех же 30 inspiration-фото.
3. **Версионируем в git** — изменения промптов = commit с обоснованием.
4. **Логируем актуальную версию prompt'а** — в `sessions.scene_quality_json` для воспроизводимости.

## Anti-patterns

- ❌ Длинные prompt'ы со списком всех возможных стилей — модель путается.
- ❌ Negative prompt длиннее основного — снижает качество.
- ❌ Включать "и пожалуйста сделай красиво" — модель reasoning'а здесь не делает.
- ❌ Динамическая длина prompt'а от 50 до 500 слов в зависимости от scene — лучше держать стабильным.
