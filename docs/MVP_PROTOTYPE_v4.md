# MVP-прототип v4: Telegram-бот для AI-вписывания товаров (OpenAI vision)

> **Использование**: Claude Code в новой папке: `прочитай MVP_PROTOTYPE_v4.md и поехали с дня 1`. Срок: **6-8 дней**. Бюджет: $200-280.

> **Главное изменение от v3**: все vision-задачи (quality check, scene analysis, product description) выполняются через **GPT-5.4 Mini** от OpenAI вместо Claude. Стоимость в 1.4× ниже, скорость выше, проще в коде благодаря native JSON mode.

> **Выбор модели**: **GPT-5.4 Mini** ($0.75/$4.50 за 1M input/output) — sweet spot для прототипа. Полная vision-поддержка, в 3× дешевле GPT-4o, в 1.4× дешевле Claude Sonnet. Если на бенчмарке quality check окажется overkill — переключаем этот шаг на GPT-5.4 Nano ($0.20/$1.25), сохраняем Mini для scene analysis.

> **Ключевая цель прототипа**: за неделю проверить даёт ли подход WOW ≥3.5/5 и success rate ≥70% на средних сценах при условии что пользователь следует инструкциям и фото нормального качества.

---

## Целевая аудитория и use case

**Платящие сегменты**: ритейлеры мебели (Hoff, Divan.ru), производители (Аскона, Mr.Doors), застройщики, дизайнеры.

**Use case**: пользователь грузит фото комнаты + фото товара → бот вписывает товар в комнату с сохранением visual identity (цвет, паттерн, форма) и контролем размера (±15%).

---

## Архитектура

```
┌──────────────────────────────────────────────────┐
│  Telegram Bot (aiogram 3)                        │
│  Long polling, без webhook                       │
└────────┬─────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  ONBOARDING (первый раз) или /help               │
│  → Tutorial с примерами фото                     │
└────────┬─────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  PIPELINE                                        │
│  Stage 0: Photo Quality Check (GPT-5.4 Mini)     │
│  Stage 1: Scene Analysis                         │
│  Stage 2: Pre-flight Size Check (algoritm)       │
│  Stage 3: Generation (FLUX Fill Pro + Redux)     │
│  Stage 4: Validation                             │
│  Stage 5: Optional Polish (Clarity Upscaler)     │
└────────┬─────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  SQLite + локальная папка                        │
└──────────────────────────────────────────────────┘
```

---

## Стек

```
Python 3.11+
aiogram 3.x
replicate                  # FLUX Fill Pro, GroundedSAM, Clarity Upscaler
openai>=1.50.0             # GPT-5.4 Mini для vision: quality check + scene + description
Pillow + numpy + opencv-python
scikit-image               # SSIM для validation
sqlite3                    # Логи
python-dotenv              # Конфиг
httpx                      # HTTP клиент
```

**Версия openai SDK**: важно ≥1.50.0 — там уже стабильная поддержка GPT-5.4 семейства. Проверить:
```bash
pip install -U openai
python -c "import openai; print(openai.__version__)"
```

---

## Структура проекта

```
mvp-prototype/
├── README.md
├── pyproject.toml
├── .env.example
├── .env
│
├── bot.py
├── states.py                # FSM
├── handlers.py
├── pipeline.py
│
├── ai/
│   ├── __init__.py
│   ├── preprocessing.py
│   ├── quality_check.py     # ⭐ NEW: проверка качества фото
│   ├── scene_analysis.py
│   ├── size_check.py
│   ├── generation.py
│   ├── validation.py
│   ├── upscaling.py
│   └── prompts.py
│
├── utils/
│   ├── storage.py
│   └── geometry.py
│
├── assets/                  # ⭐ NEW: visual assets для онбординга
│   ├── tutorial/
│   │   ├── 01_intro.jpg     # картинка "как это работает" — до/после
│   │   ├── 02_scene_good_bad.jpg   # примеры сцен ✅/❌
│   │   ├── 03_product_good_bad.jpg # примеры товаров ✅/❌
│   │   └── 04_size_help.jpg # как мерить размеры
│   └── README.md            # инструкция по подготовке assets
│
├── data/
│   ├── test_inspirations/
│   │   ├── easy/            # 10 простых
│   │   ├── medium/          # 15 средних
│   │   └── hard/            # 5 сложных
│   ├── test_catalog/        # 20 фото товаров с размерами в имени
│   └── results/
│
├── db.py
├── metrics.py
│
└── scripts/
    ├── benchmark.py
    └── eval_results.py
```

---

## .env конфиг

```bash
TG_BOT_TOKEN=...                 # @BotFather
REPLICATE_API_TOKEN=r8_...       # replicate.com/account
OPENAI_API_KEY=sk-...            # platform.openai.com/api-keys
ADMIN_TG_ID=...                  
TEST_MODE=true                   
COST_LIMIT_USD=300               
SIZE_TOLERANCE_PCT=15            

# Модели OpenAI (можно переопределить для бенчмарка)
OPENAI_VISION_MODEL=gpt-5.4-mini       # для всех vision-задач по умолчанию
OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-mini # можно переключить на gpt-5.4-nano для экономии
QUALITY_CHECK_ENABLED=true       
SKIP_ONBOARDING_FOR_DEV=false    
```

---

## Visual Assets для онбординга — что нужно подготовить

⭐ **Это новая важная часть прототипа.** Без них онбординг не работает.

Claude Code в день 6 спросит у тебя: «нужно собрать 4 картинки для туториала, какой подход?»

Варианты:
1. **Найти готовые в интернете** (Pinterest, Unsplash) — бесплатно, быстро
2. **Сгенерировать FLUX'ом по описаниям** — стоит $0.40, можно итеративно
3. **Сделать в Figma композит из реальных скриншотов** — лучшее качество, час работы

Рекомендую **вариант 3** для финала, **вариант 1+2** для первой итерации.

### Asset 1: `01_intro.jpg` — «как это работает»

Композит "до/после":
- Слева: фото комнаты с диваном (inspiration)
- Стрелка с надписью «+ фото товара»
- Справа: та же комната, но с другим, конкретным диваном (наш товар)

Подпись: **«AI заменит мебель на ваш конкретный товар»**

### Asset 2: `02_scene_good_bad.jpg` — фото сцены ✅/❌

Композит 4 картинок (2x2):

**✅ Хорошие сцены:**
- Гостиная снятая от двери, дневной свет, виден весь интерьер
- Спальня нормального освещения с явной кроватью

**❌ Плохие сцены:**
- Тёмная комната без света (трудно AI работать)
- Снято близко, видна только часть мебели

Подпись на каждой ясная: «✅ Дневной свет, видна вся комната» / «❌ Слишком темно».

### Asset 3: `03_product_good_bad.jpg` — фото товара ✅/❌

Композит 4 картинок:

**✅ Хорошие товары:**
- Диван на белом фоне как в каталоге Hoff
- Кресло на нейтральном фоне, видна вся форма

**❌ Плохие товары:**
- Скриншот товара с маркетплейса с ценником и кнопками
- Товар в сложной обстановке среди других предметов

### Asset 4: `04_size_help.jpg` — как мерить

Простая иллюстрация:
- Комната с указанными размерами (длина × ширина)
- Диван с указанными размерами (длина × глубина × высота)
- Подпись «Размеры можно посмотреть в карточке товара на сайте магазина»

---

## Onboarding flow (НОВОЕ)

При **первом** /start пользователь видит туториал. При повторном — сразу к делу. Команда `/help` показывает туториал в любой момент.

```
/start (первый раз)
  ↓
[Asset 1: до/после]
"👋 Привет! Я AI-помощник для вписывания товаров в интерьер.

Покажу как ваш товар (диван, кресло, лампа) будет смотреться 
в реальной комнате. Это полезно для:
• Маркетинга — красивые картинки товара в интерьере
• Дизайна — клиент сразу видит как будет выглядеть
• Продажи квартиры — обстановка повышает интерес

[Понятно] [Подробнее]"
  ↓
[Asset 2: scene ✅/❌]
"📷 ФОТО СЦЕНЫ (комнаты, в которую вписываем):

✅ Хорошо:
• Дневной свет
• Видна вся комната (от двери)
• Чёткое изображение
• Простой угол съёмки

❌ Не подойдёт:
• Очень тёмное фото
• Только угол комнаты виден
• Размытое
• С искажениями (рыбий глаз)

[Дальше]"
  ↓
[Asset 3: product ✅/❌]
"🛋 ФОТО ТОВАРА (что вписываем):

✅ Хорошо:
• Каталожное фото на белом фоне
• Один товар на картинке
• Виден целиком
• Высокое качество

❌ Не подойдёт:
• Скриншот с маркетплейса с ценником
• Товар в сложной обстановке
• Только часть видна
• Низкое качество

[Дальше]"
  ↓
[Asset 4: размеры]
"📏 РАЗМЕРЫ (опционально, но желательно):

• Размеры комнаты в метрах (длина × ширина) — для масштаба
• Размеры товара в см (длина × глубина × высота)

Это сильно улучшает результат. Размеры берутся из карточки товара 
на сайте Hoff/Wildberries/Ozon.

Если не знаете — напишите 'не знаю', я оценю по фото 
(точность будет ниже).

[Понятно, поехали!]"
  ↓
[Запуск основного flow]
```

После прохождения туториала факт сохраняется в БД, при повторных /start — скипается.

**Команды бота**:
- `/start` — старт работы (с туториалом если первый раз)
- `/help` — показать туториал снова
- `/cancel` — прервать текущий процесс
- `/myhistory` — последние 5 регенераций (для оценки/сравнения)

---

## Photo Quality Check (НОВОЕ)

⭐ **Stage 0 в pipeline.** Сразу после загрузки фото бот проверяет его качество через GPT-5.4 Mini vision и предупреждает пользователя о проблемах.

```python
# ai/quality_check.py
import os
import json
from openai import AsyncOpenAI

client = AsyncOpenAI()
QUALITY_MODEL = os.environ.get("OPENAI_QUALITY_CHECK_MODEL", "gpt-5.4-mini")

QUALITY_CHECK_SCENE_PROMPT = """Ты проверяешь фото интерьера для AI-обработки.

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

QUALITY_CHECK_PRODUCT_PROMPT = """Ты проверяешь фото товара (мебели/декора) для AI-обработки.

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


async def check_scene_quality(image_url: str) -> dict:
    """Проверка качества фото сцены через GPT-5.4 Mini vision."""
    response = await client.chat.completions.create(
        model=QUALITY_MODEL,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": QUALITY_CHECK_SCENE_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "low",  # 512×512 — для quality check достаточно, дешевле
                    }
                },
            ]
        }],
        max_tokens=600,
    )
    return json.loads(response.choices[0].message.content)


async def check_product_quality(image_url: str) -> dict:
    """Проверка качества фото товара через GPT-5.4 Mini vision."""
    response = await client.chat.completions.create(
        model=QUALITY_MODEL,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": QUALITY_CHECK_PRODUCT_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "low",
                    }
                },
            ]
        }],
        max_tokens=600,
    )
    return json.loads(response.choices[0].message.content)
```

**Логика обработки результатов**:

| Recommendation | Действие бота |
|---|---|
| `proceed` | Продолжаем без вопросов |
| `warn_user` | Показываем предупреждение + кнопки [Всё равно делать] [Загрузить другое фото] |
| `reject` | Отклоняем, просим загрузить другое фото |

**Стоимость**: 1 проверка = $0.003 (Claude Sonnet vision). На полный flow добавляет $0.006 (сцена + товар).

---

## Полный Bot Flow (с онбордингом и quality check)

```
/start
  ↓
[если первый раз] → ОНБОРДИНГ (4 картинки + объяснения)
[если не первый] → "С возвращением! Загрузите фото комнаты."
  ↓
[пользователь грузит фото СЦЕНЫ]
  ↓
⏳ "Проверяю качество фото (3 сек)..."
  ↓
[Stage 0: quality check]
  ├── proceed → "✓ Сцена принята"
  ├── warn → "⚠️ Фото немного тёмное, может работать хуже. 
  │           [Всё равно делать] [Загрузить другое]"
  └── reject → "❌ Это не похоже на фото интерьера. Загрузите другое."
  ↓
"Размеры комнаты в метрах? Например 5x4. Или 'не знаю'."
  ↓
[пользователь отвечает]
  ↓
"Какой объект заменить? sofa / armchair / bed / lamp / etc"
  ↓
[пользователь отвечает]
  ↓
"Загрузите фото товара (как в каталоге Hoff/WB/Ozon)"
  ↓
[пользователь грузит]
  ↓
⏳ "Проверяю фото товара (3 сек)..."
  ↓
[Stage 0: quality check для товара]
  ├── proceed → "✓ Товар принят"
  ├── warn → "⚠️ На фото несколько предметов. Лучше один товар на белом фоне.
  │           [Всё равно делать] [Загрузить другое]"
  └── reject → "❌ Это не похоже на фото мебели/товара. Загрузите другое."
  ↓
"Размеры товара в см (длина x глубина x высота)? 
Например 220x90x85. Или 'не знаю'."
  ↓
[пользователь отвечает]
  ↓
⏳ "Анализирую сцену и проверяю размеры (10-15 сек)..."
  ↓
[Stage 1: Scene Analysis + Detection]
[Stage 2: Pre-flight Size Check]
  ↓
КЕЙС A: размеры подходят
  → "✅ Размеры подходят. Генерирую (45-60 сек)..."

КЕЙС B: размеры на грани
  → "⚠️ Товар чуть больше слота на 25%. 
     [Всё равно делать] [Загрузить другой товар]"

КЕЙС C: размеры не подходят
  → "❌ Товар физически не вписывается:
     Слот ~250x95 см, ваш товар 350x120 см (+40%).
     [Всё равно делать] [Загрузить другой товар]"

КЕЙС D: не нашли слот
  → "❌ Не вижу подходящего места для {target_class} в этой сцене.
     Попробуйте другой объект или другую сцену."
  ↓
[Stage 3-5 если решили продолжать]
  ↓
"✨ Готово! [картинка]
WOW: 4.2/5
Visual identity: 0.81
Presence: 0.92  
Size match: 8% deviation

[👍 Отлично] [😐 Средне] [👎 Плохо] [Заметка] [Ещё раз]"
```

**Лимиты**: 5 регенераций / пользователь / день.

---

## Pipeline — детально

### Stage 0: Photo Quality Check

См. выше `ai/quality_check.py`.

### Stage 1: Scene Analysis

```python
# ai/scene_analysis.py
import os
import json
import replicate
from openai import AsyncOpenAI

client = AsyncOpenAI()
VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-5.4-mini")

CLAUDE_SCENE_PROMPT = """Проанализируй фото интерьера для AI-обработки. Верни строго JSON:

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
"""


async def analyze_scene(image_url: str) -> dict:
    """Анализ сцены через GPT-5.4 Mini vision."""
    response = await client.chat.completions.create(
        model=VISION_MODEL,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": CLAUDE_SCENE_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "high",  # детали важны для определения ориентиров (двери, окна)
                    }
                },
            ]
        }],
        max_tokens=1500,
    )
    return json.loads(response.choices[0].message.content)


async def detect_target_slot(image_url: str, target_class: str) -> dict:
    """GroundedSAM находит слот для замены"""
    out = await replicate.async_run(
        "schananas/grounded_sam",
        input={
            "image": image_url,
            "mask_prompt": target_class,
            "negative_mask_prompt": "wall, floor, ceiling, window, door",
            "adjustment_factor": 12,
        },
    )
    return {
        "mask_url": out.get("masked_img"),
        "bbox": out.get("bbox"),
        "found": out.get("masked_img") is not None,
    }
```

### Stage 2: Pre-flight Size Check

```python
# ai/size_check.py
import numpy as np
from PIL import Image
import requests
from io import BytesIO


def estimate_slot_dimensions(
    bbox: list,
    scene_image_url: str,
    room_dimensions_m: tuple = None,
    scene_analysis: dict = None,
) -> dict:
    """Оценка реальных размеров слота"""
    img = Image.open(BytesIO(requests.get(scene_image_url).content))
    img_w, img_h = img.size
    
    bbox_w_px = bbox[2] - bbox[0]
    bbox_h_px = bbox[3] - bbox[1]
    
    if room_dimensions_m:
        # Пользователь дал точные размеры
        room_long_side = max(room_dimensions_m)
        scene_width_m = room_long_side * 0.75  # ~75% длинной стены в кадре
        m_per_px = scene_width_m / img_w
        
        slot_width_cm = bbox_w_px * m_per_px * 100
        slot_height_cm = bbox_h_px * m_per_px * 100
        slot_depth_cm = slot_width_cm * 0.5  # эвристика
        confidence = "high"
        
    elif scene_analysis and "scale_references" in scene_analysis:
        # Используем подсказки из Claude (дверь, окно, плинтус)
        slot_width_cm, slot_height_cm, slot_depth_cm = estimate_from_references(
            bbox, img_w, img_h, scene_analysis
        )
        confidence = "medium"
        
    else:
        # Грубая оценка по типу комнаты
        room_type_defaults = {
            "living_room": (5.0, 4.0),
            "bedroom": (4.0, 3.5),
            "kitchen": (4.0, 3.0),
            "bathroom": (2.5, 2.0),
            "office": (4.0, 3.0),
        }
        room_type = scene_analysis.get("room_type", "living_room") if scene_analysis else "living_room"
        long, _ = room_type_defaults.get(room_type, (4.5, 3.5))
        scene_width_m = long * 0.75
        m_per_px = scene_width_m / img_w
        slot_width_cm = bbox_w_px * m_per_px * 100
        slot_height_cm = bbox_h_px * m_per_px * 100
        slot_depth_cm = slot_width_cm * 0.5
        confidence = "low"
    
    return {
        "width_cm": int(slot_width_cm),
        "height_cm": int(slot_height_cm),
        "depth_cm": int(slot_depth_cm),
        "confidence": confidence,
        "bbox_px": bbox,
    }


def estimate_from_references(bbox, img_w, img_h, scene_analysis):
    """Использует scale_references (door, window) для оценки"""
    refs = scene_analysis.get("scale_references", [])
    
    # Простая логика: ищем дверь (200 см) или окно (80 см подоконник)
    # Если есть — используем как референс
    # В прототипе это упрощённо. В production — детектируем дверь через GroundedSAM.
    
    # Дефолт: предполагаем что фото покрывает 4-5 м в ширину
    bbox_w_px = bbox[2] - bbox[0]
    bbox_h_px = bbox[3] - bbox[1]
    scene_width_m = 4.5
    m_per_px = scene_width_m / img_w
    
    return (
        int(bbox_w_px * m_per_px * 100),
        int(bbox_h_px * m_per_px * 100),
        int(bbox_w_px * m_per_px * 100 * 0.5),
    )


def check_fit(
    product_dims_cm: tuple,
    slot_dims: dict,
    tolerance_pct: int = 15,
) -> dict:
    """Проверяет вписывается ли товар в слот"""
    p_length, p_depth, p_height = product_dims_cm
    
    deviations = {
        "width": ((p_length - slot_dims["width_cm"]) / slot_dims["width_cm"]) * 100,
        "height": ((p_height - slot_dims["height_cm"]) / slot_dims["height_cm"]) * 100,
        "depth": ((p_depth - slot_dims["depth_cm"]) / slot_dims["depth_cm"]) * 100,
    }
    
    max_abs_dev = max(abs(d) for d in deviations.values())
    
    if max_abs_dev <= tolerance_pct:
        verdict = "perfect"
        fits = True
        explanation = f"Товар отлично вписывается (макс. отклонение {max_abs_dev:.0f}%)"
    elif max_abs_dev <= tolerance_pct * 2:  # 30%
        verdict = "acceptable"
        fits = True
        explanation = f"Вписывается с погрешностью {max_abs_dev:.0f}%"
    elif max_abs_dev <= tolerance_pct * 3:  # 45%
        verdict = "marginal"
        fits = False
        explanation = f"Размер сильно отличается ({max_abs_dev:.0f}%). Может выглядеть не натурально."
    else:
        verdict = "doesnt_fit"
        fits = False
        explanation = f"Не вписывается ({max_abs_dev:.0f}% отклонение). Нужен другой товар."
    
    return {
        "fits": fits,
        "deviation_pct": deviations,
        "max_deviation": max_abs_dev,
        "verdict": verdict,
        "explanation": explanation,
        "slot_dims_cm": slot_dims,
        "product_dims_cm": product_dims_cm,
    }
```

### Stage 3: Generation

```python
# ai/generation.py
import replicate

NEGATIVE_PROMPT = (
    "deformed, distorted, blurry, cartoon, oversaturated, plastic look, "
    "fake, CGI, warped perspective, floating furniture, duplicated objects, "
    "melting furniture, mismatched scale, watermark, text, logo, low quality"
)


async def describe_product(product_url: str) -> str:
    """GPT-5.4 Mini vision описывает товар структурированно для prompt."""
    from openai import AsyncOpenAI
    import os
    
    client = AsyncOpenAI()
    model = os.environ.get("OPENAI_VISION_MODEL", "gpt-5.4-mini")
    
    response = await client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Опиши этот предмет мебели для AI image generation prompt. "
                    "Включи: тип, цвет, материал/обивку, узор/паттерн (если есть), "
                    "форму, стиль ножек/основания, особые детали. "
                    "Кратко, до 60 слов, на английском, без preamble."
                )},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": product_url,
                        "detail": "low",  # для описания товара low достаточно
                    }
                },
            ]
        }],
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


async def generate_with_fill_pro(
    scene_url: str,
    mask_url: str,
    product_url: str,
    target_class: str,
    product_description: str,
    scene_analysis: dict,
    seed: int = 42,
) -> str:
    """FLUX Fill Pro inpainting с reference из каталога"""
    
    style = scene_analysis.get("style", "modern")
    lighting = scene_analysis.get("lighting", "natural_daylight")
    
    prompt = (
        f"a {target_class} that matches the reference product exactly. "
        f"{product_description}. "
        f"{style} interior style, {lighting} lighting matching the room. "
        f"photorealistic, sharp focus, high detail, magazine-quality interior photography. "
        f"the {target_class} should fit naturally into the existing room geometry."
    )
    
    result = await replicate.async_run(
        "black-forest-labs/flux-fill-pro",
        input={
            "image": scene_url,
            "mask": mask_url,
            "prompt": prompt,
            "guidance": 30,
            "num_inference_steps": 30,
            "safety_tolerance": 2,
            "output_format": "png",
            "seed": seed,
        },
    )
    return result if isinstance(result, str) else result[0]
```

### Stage 4: Validation

```python
# ai/validation.py
import numpy as np
import replicate
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import requests
from io import BytesIO


async def validate_result(
    result_url: str,
    target_class: str,
    product_url: str,
    scene_url: str,
    slot_bbox: list = None,
) -> dict:
    # 1. Presence через Grounding DINO
    detect = await replicate.async_run(
        "adirik/grounding-dino",
        input={
            "image": result_url,
            "query": target_class,
            "box_threshold": 0.30,
            "text_threshold": 0.25,
        },
    )
    detections = detect.get("detections", [])
    presence_conf = max([d.get("score", 0) for d in detections] or [0])
    
    # 2. Position check
    position_ok = True
    if slot_bbox and detections:
        ious = [compute_iou(d.get("bbox", [0, 0, 0, 0]), slot_bbox) for d in detections]
        position_ok = max(ious) > 0.3 if ious else False
    
    # 3. Catalog fidelity (CLIP-I)
    emb_result = await replicate.async_run(
        "andreasjansson/clip-features",
        input={"inputs": result_url},
    )
    emb_product = await replicate.async_run(
        "andreasjansson/clip-features",
        input={"inputs": product_url},
    )
    e1 = np.array(emb_result[0]["embedding"])
    e2 = np.array(emb_product[0]["embedding"])
    catalog_sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))
    
    # 4. Scene preservation (SSIM)
    img_orig = np.array(Image.open(BytesIO(requests.get(scene_url).content)).convert("L"))
    img_result = np.array(Image.open(BytesIO(requests.get(result_url).content)).convert("L"))
    
    if img_orig.shape != img_result.shape:
        img_result = np.array(Image.fromarray(img_result).resize(img_orig.shape[::-1]))
    ssim_score = float(ssim(img_orig, img_result, data_range=255))
    
    # 5. Aesthetic placeholder
    aesthetic = 5.0
    
    # WOW score
    wow_score = (
        catalog_sim * 0.4 +
        (presence_conf if presence_conf >= 0.4 else 0) * 0.3 +
        (aesthetic / 10) * 0.2 +
        (ssim_score if ssim_score >= 0.7 else 0) * 0.1
    ) * 5
    
    passed = (
        presence_conf >= 0.4 and
        catalog_sim >= 0.65 and
        ssim_score >= 0.70 and
        position_ok
    )
    
    return {
        "passed": passed,
        "presence_conf": presence_conf,
        "catalog_sim": catalog_sim,
        "ssim_score": ssim_score,
        "aesthetic": aesthetic,
        "position_ok": position_ok,
        "wow_score": wow_score,
    }


def compute_iou(box1: list, box2: list) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    if x2 < x1 or y2 < y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0
```

### Stage 5: Optional Polish

```python
# ai/upscaling.py
async def upscale_final(image_url: str, scale: int = 2) -> str:
    out = await replicate.async_run(
        "philz1337x/clarity-upscaler",
        input={
            "image": image_url,
            "prompt": "masterpiece, best quality, photorealistic interior",
            "negative_prompt": "blurry, low quality, watermark, text",
            "scale_factor": scale,
            "creativity": 0.35,
            "resemblance": 0.6,
            "num_inference_steps": 18,
        },
    )
    return out if isinstance(out, str) else out[0]
```

---

## Главный orchestrator

```python
# pipeline.py
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def process_user_request(
    scene_url: str,
    product_url: str,
    target_class: str,
    room_dimensions_m: tuple = None,
    product_dims_cm: tuple = None,
    n_seeds: int = 3,
    skip_quality_check: bool = False,
    skip_size_check: bool = False,
) -> dict:
    """
    Главный orchestrator. Возвращает {success, url, validation, cost, ...}.
    """
    cost_estimate = 0.0
    
    # === Stage 0: Quality checks (если не пропущены) ===
    if not skip_quality_check:
        scene_qc = await check_scene_quality(scene_url)
        cost_estimate += 0.002  # GPT-5.4 Mini vision (low detail)
        
        if scene_qc.get("recommendation") == "reject":
            return {
                "success": False,
                "error": "scene_rejected",
                "message": scene_qc.get("user_message", "Фото не подходит"),
                "cost": cost_estimate,
            }
        
        product_qc = await check_product_quality(product_url)
        cost_estimate += 0.002
        
        if product_qc.get("recommendation") == "reject":
            return {
                "success": False,
                "error": "product_rejected",
                "message": product_qc.get("user_message", "Фото товара не подходит"),
                "cost": cost_estimate,
            }
        
        warnings = []
        if scene_qc.get("recommendation") == "warn_user":
            warnings.append(("scene", scene_qc.get("user_message")))
        if product_qc.get("recommendation") == "warn_user":
            warnings.append(("product", product_qc.get("user_message")))
    else:
        warnings = []
    
    # === Stage 1: Scene Analysis ===
    scene_analysis = await analyze_scene(scene_url)
    cost_estimate += 0.003  # GPT-5.4 Mini vision (high detail)
    
    slot_detection = await detect_target_slot(scene_url, target_class)
    cost_estimate += 0.005
    
    if not slot_detection["found"]:
        return {
            "success": False,
            "error": "no_slot_detected",
            "message": (
                f"Не нашёл подходящего места для {target_class} в этой сцене. "
                f"Попробуйте другой объект или другое фото."
            ),
            "cost": cost_estimate,
            "warnings": warnings,
        }
    
    # === Stage 2: Pre-flight Size Check ===
    size_check_result = None
    if not skip_size_check and product_dims_cm:
        slot_dims = estimate_slot_dimensions(
            slot_detection["bbox"], scene_url,
            room_dimensions_m=room_dimensions_m,
            scene_analysis=scene_analysis,
        )
        size_check_result = check_fit(
            product_dims_cm, slot_dims,
            tolerance_pct=int(os.environ.get("SIZE_TOLERANCE_PCT", "15")),
        )
        
        if size_check_result["verdict"] in ["doesnt_fit", "marginal"]:
            return {
                "success": False,
                "error": "size_mismatch",
                "size_check": size_check_result,
                "message": size_check_result["explanation"],
                "cost": cost_estimate,
                "warnings": warnings,
            }
    
    # === Stage 3: Generation ===
    product_desc = await describe_product(product_url)
    cost_estimate += 0.001  # GPT-5.4 Mini vision (low detail)
    
    candidates = []
    for s in range(n_seeds):
        try:
            gen = await generate_with_fill_pro(
                scene_url=scene_url,
                mask_url=slot_detection["mask_url"],
                product_url=product_url,
                target_class=target_class,
                product_description=product_desc,
                scene_analysis=scene_analysis,
                seed=42 + s,
            )
            cost_estimate += 0.05
            
            v = await validate_result(
                gen, target_class, product_url, scene_url,
                slot_bbox=slot_detection["bbox"],
            )
            cost_estimate += 0.01
            
            candidates.append((v["wow_score"], gen, v))
        except Exception as e:
            logger.error(f"Generation failed seed={s}: {e}")
            continue
    
    if not candidates:
        return {
            "success": False,
            "error": "all_seeds_failed",
            "cost": cost_estimate,
            "warnings": warnings,
        }
    
    candidates.sort(reverse=True, key=lambda x: x[0])
    _, best_url, best_val = candidates[0]
    variants = [c[1] for c in candidates[:3]]
    
    # === Stage 5: Upscale ===
    if best_val["passed"]:
        try:
            best_url = await upscale_final(best_url, scale=2)
            cost_estimate += 0.016
        except Exception as e:
            logger.warning(f"Upscale failed, skipping: {e}")
    
    return {
        "success": True,
        "url": best_url,
        "variants": variants,
        "validation": best_val,
        "size_check": size_check_result,
        "scene_analysis": scene_analysis,
        "cost": cost_estimate,
        "warnings": warnings,
    }
```

---

## SQLite logging

```python
# db.py
import sqlite3
import json
from datetime import datetime

DB_PATH = "data/prototype.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            tg_user_id INTEGER PRIMARY KEY,
            username TEXT,
            onboarded BOOLEAN DEFAULT FALSE,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_generations INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER,
            scene_url TEXT,
            product_url TEXT,
            target_class TEXT,
            room_dims_m TEXT,
            product_dims_cm TEXT,
            scene_quality_json TEXT,
            product_quality_json TEXT,
            scene_analysis_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            success BOOLEAN,
            error_type TEXT,
            result_url TEXT,
            variants_json TEXT,
            validation_json TEXT,
            size_check_json TEXT,
            wow_score REAL,
            cost_usd REAL,
            duration_sec INTEGER,
            user_rating TEXT,
            user_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()
    conn.close()


def is_user_onboarded(tg_user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT onboarded FROM users WHERE tg_user_id = ?", (tg_user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def mark_user_onboarded(tg_user_id: int, username: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO users (tg_user_id, username, onboarded, first_seen, last_seen)
        VALUES (?, ?, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(tg_user_id) DO UPDATE SET 
            onboarded = TRUE,
            last_seen = CURRENT_TIMESTAMP
    """, (tg_user_id, username))
    conn.commit()
    conn.close()


def log_session(tg_user_id, scene_url, product_url, target_class,
                room_dims, product_dims, scene_qc, product_qc, scene_analysis):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sessions 
        (tg_user_id, scene_url, product_url, target_class, room_dims_m, 
         product_dims_cm, scene_quality_json, product_quality_json, scene_analysis_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tg_user_id, scene_url, product_url, target_class,
        json.dumps(room_dims) if room_dims else None,
        json.dumps(product_dims) if product_dims else None,
        json.dumps(scene_qc) if scene_qc else None,
        json.dumps(product_qc) if product_qc else None,
        json.dumps(scene_analysis) if scene_analysis else None,
    ))
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def log_generation(session_id, result, duration):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO generations 
        (session_id, success, error_type, result_url, variants_json, 
         validation_json, size_check_json, wow_score, cost_usd, duration_sec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        result.get("success", False),
        result.get("error"),
        result.get("url"),
        json.dumps(result.get("variants", [])),
        json.dumps(result.get("validation")) if result.get("validation") else None,
        json.dumps(result.get("size_check")) if result.get("size_check") else None,
        result.get("validation", {}).get("wow_score") if result.get("validation") else None,
        result.get("cost"),
        duration,
    ))
    gen_id = cur.lastrowid
    conn.commit()
    conn.close()
    return gen_id


def update_user_rating(generation_id: int, rating: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE generations SET user_rating = ? WHERE id = ?", (rating, generation_id))
    conn.commit()
    conn.close()
```

---

## Bot handlers — полная реализация

```python
# bot.py
import os
import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from pipeline import process_user_request
from db import (
    init_db, is_user_onboarded, mark_user_onboarded,
    log_session, log_generation, update_user_rating
)
from ai.preprocessing import preprocess_image
from utils.storage import upload_to_temp_storage

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.environ["TG_BOT_TOKEN"])
dp = Dispatcher(storage=MemoryStorage())

ASSETS_DIR = "assets/tutorial"


class GenStates(StatesGroup):
    onboarding_step_1 = State()
    onboarding_step_2 = State()
    onboarding_step_3 = State()
    onboarding_step_4 = State()
    waiting_scene = State()
    waiting_room_dims = State()
    waiting_target_class = State()
    waiting_product_photo = State()
    waiting_product_dims = State()
    confirming_warning = State()


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    if not is_user_onboarded(message.from_user.id):
        # Первый раз — показать туториал
        await show_onboarding_step_1(message, state)
    else:
        # Знакомый пользователь — сразу к делу
        await message.answer(
            "👋 С возвращением!\n\n"
            "Загрузите фото комнаты, в которую будем вписывать товар.\n"
            "(Команда /help — показать туториал заново)"
        )
        await state.set_state(GenStates.waiting_scene)


@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await show_onboarding_step_1(message, state)


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. Команда /start чтобы начать заново.")


async def show_onboarding_step_1(message: Message, state: FSMContext):
    photo = FSInputFile(f"{ASSETS_DIR}/01_intro.jpg")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Понятно, дальше →", callback_data="onb:next:2")
    
    await message.answer_photo(
        photo,
        caption=(
            "👋 Я AI-помощник для вписывания товаров в интерьер.\n\n"
            "Покажу как ваш товар (диван, кресло, лампа) "
            "будет смотреться в реальной комнате.\n\n"
            "Полезно для:\n"
            "• 📸 Маркетинга — красивые картинки в интерьере\n"
            "• 🎨 Дизайна — клиент сразу видит результат\n"
            "• 🏠 Продажи квартиры — обстановка повышает интерес"
        ),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(GenStates.onboarding_step_1)


@dp.callback_query(F.data == "onb:next:2")
async def onboarding_step_2(callback: CallbackQuery, state: FSMContext):
    photo = FSInputFile(f"{ASSETS_DIR}/02_scene_good_bad.jpg")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Понятно, дальше →", callback_data="onb:next:3")
    
    await callback.message.answer_photo(
        photo,
        caption=(
            "📷 ФОТО СЦЕНЫ (комнаты, в которую вписываем):\n\n"
            "✅ Хорошо:\n"
            "• Дневной свет\n"
            "• Видна вся комната\n"
            "• Чёткое изображение\n"
            "• Простой угол съёмки\n\n"
            "❌ Не подойдёт:\n"
            "• Очень тёмное фото\n"
            "• Только угол комнаты\n"
            "• Размытое\n"
            "• Сильные искажения (рыбий глаз)"
        ),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(GenStates.onboarding_step_2)


@dp.callback_query(F.data == "onb:next:3")
async def onboarding_step_3(callback: CallbackQuery, state: FSMContext):
    photo = FSInputFile(f"{ASSETS_DIR}/03_product_good_bad.jpg")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Понятно, дальше →", callback_data="onb:next:4")
    
    await callback.message.answer_photo(
        photo,
        caption=(
            "🛋 ФОТО ТОВАРА (что вписываем):\n\n"
            "✅ Хорошо:\n"
            "• Каталожное фото на белом фоне\n"
            "• Один товар на картинке\n"
            "• Виден целиком\n"
            "• Высокое качество\n\n"
            "❌ Не подойдёт:\n"
            "• Скриншот с маркетплейса с ценником\n"
            "• Товар в сложной обстановке\n"
            "• Только часть видна\n"
            "• Низкое качество"
        ),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(GenStates.onboarding_step_3)


@dp.callback_query(F.data == "onb:next:4")
async def onboarding_step_4(callback: CallbackQuery, state: FSMContext):
    photo = FSInputFile(f"{ASSETS_DIR}/04_size_help.jpg")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Понятно, поехали! 🚀", callback_data="onb:done")
    
    await callback.message.answer_photo(
        photo,
        caption=(
            "📏 РАЗМЕРЫ (опционально, но желательно):\n\n"
            "• Размеры комнаты в метрах (длина × ширина)\n"
            "• Размеры товара в см (длина × глубина × высота)\n\n"
            "Это сильно улучшает результат. Размеры берутся "
            "из карточки товара на сайте магазина.\n\n"
            "Если не знаете — напишите 'не знаю', "
            "оценю примерно по фото."
        ),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(GenStates.onboarding_step_4)


@dp.callback_query(F.data == "onb:done")
async def onboarding_done(callback: CallbackQuery, state: FSMContext):
    mark_user_onboarded(callback.from_user.id, callback.from_user.username or "")
    
    await callback.message.answer(
        "🚀 Готово! Загрузите фото комнаты, в которую вписываем товар."
    )
    await state.set_state(GenStates.waiting_scene)


@dp.message(GenStates.waiting_scene, F.photo)
async def receive_scene(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    processed = preprocess_image(file_bytes.read())
    scene_url = await upload_to_temp_storage(processed)
    
    # Quality check
    await message.answer("⏳ Проверяю фото (3 сек)...")
    
    from ai.quality_check import check_scene_quality
    qc = await check_scene_quality(scene_url)
    
    if qc.get("recommendation") == "reject":
        await message.answer(
            f"❌ {qc.get('user_message', 'Это фото не подходит')}\n\n"
            f"Загрузите другое фото комнаты."
        )
        return  # state остаётся waiting_scene, ждём другое
    
    await state.update_data(scene_url=scene_url, scene_qc=qc)
    
    if qc.get("recommendation") == "warn_user":
        kb = InlineKeyboardBuilder()
        kb.button(text="✓ Всё равно делать", callback_data="qc_scene:proceed")
        kb.button(text="↻ Загрузить другое", callback_data="qc_scene:retry")
        
        await message.answer(
            f"⚠️ {qc.get('user_message')}\n\n"
            f"Что делаем?",
            reply_markup=kb.as_markup(),
        )
        return
    
    # Proceed
    await ask_room_dims(message, state)


@dp.callback_query(F.data == "qc_scene:proceed")
async def qc_scene_proceed(callback: CallbackQuery, state: FSMContext):
    await ask_room_dims(callback.message, state)


@dp.callback_query(F.data == "qc_scene:retry")
async def qc_scene_retry(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Загрузите другое фото комнаты.")
    # state остаётся waiting_scene


async def ask_room_dims(message: Message, state: FSMContext):
    await message.answer(
        "✓ Сцена принята.\n\n"
        "Размеры комнаты в метрах? (длина × ширина)\n"
        "Например: 5x4\n"
        "Или напишите 'не знаю'."
    )
    await state.set_state(GenStates.waiting_room_dims)


@dp.message(GenStates.waiting_room_dims, F.text)
async def receive_room_dims(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    room_dims = None
    
    if text not in ["не знаю", "skip", "нет"]:
        try:
            parts = text.replace("х", "x").replace("×", "x").split("x")
            room_dims = (float(parts[0]), float(parts[1]))
            if any(d < 1 or d > 30 for d in room_dims):
                raise ValueError("unrealistic")
        except (ValueError, IndexError):
            await message.answer(
                "Не понял формат. Напишите как: 5x4 или 'не знаю'."
            )
            return
    
    await state.update_data(room_dims=room_dims)
    await message.answer(
        "Какой объект заменить/вписать?\n"
        "На английском, примеры: sofa, armchair, bed, coffee table, lamp, rug, wardrobe."
    )
    await state.set_state(GenStates.waiting_target_class)


@dp.message(GenStates.waiting_target_class, F.text)
async def receive_target_class(message: Message, state: FSMContext):
    target_class = message.text.strip().lower()
    if not target_class or len(target_class) > 50:
        await message.answer("Не могу распознать. Попробуйте проще: sofa, lamp, rug.")
        return
    
    await state.update_data(target_class=target_class)
    await message.answer(
        f"✓ Заменяем: {target_class}\n\n"
        "Загрузите фото товара (как в каталоге Hoff/WB/Ozon)."
    )
    await state.set_state(GenStates.waiting_product_photo)


@dp.message(GenStates.waiting_product_photo, F.photo)
async def receive_product_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    processed = preprocess_image(file_bytes.read())
    product_url = await upload_to_temp_storage(processed)
    
    # Quality check
    await message.answer("⏳ Проверяю фото товара (3 сек)...")
    
    from ai.quality_check import check_product_quality
    qc = await check_product_quality(product_url)
    
    if qc.get("recommendation") == "reject":
        await message.answer(
            f"❌ {qc.get('user_message', 'Фото товара не подходит')}\n\n"
            f"Загрузите другое."
        )
        return
    
    await state.update_data(product_url=product_url, product_qc=qc)
    
    if qc.get("recommendation") == "warn_user":
        kb = InlineKeyboardBuilder()
        kb.button(text="✓ Всё равно делать", callback_data="qc_product:proceed")
        kb.button(text="↻ Загрузить другое", callback_data="qc_product:retry")
        
        await message.answer(
            f"⚠️ {qc.get('user_message')}\n\n"
            f"Что делаем?",
            reply_markup=kb.as_markup(),
        )
        return
    
    await ask_product_dims(message, state)


@dp.callback_query(F.data == "qc_product:proceed")
async def qc_product_proceed(callback: CallbackQuery, state: FSMContext):
    await ask_product_dims(callback.message, state)


@dp.callback_query(F.data == "qc_product:retry")
async def qc_product_retry(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Загрузите другое фото товара.")


async def ask_product_dims(message: Message, state: FSMContext):
    await message.answer(
        "✓ Товар принят.\n\n"
        "Размеры товара в см? (длина × глубина × высота)\n"
        "Например: 220x90x85\n"
        "Или 'не знаю'."
    )
    await state.set_state(GenStates.waiting_product_dims)


@dp.message(GenStates.waiting_product_dims, F.text)
async def receive_product_dims(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    product_dims = None
    
    if text not in ["не знаю", "skip", "нет"]:
        try:
            parts = text.replace("х", "x").replace("×", "x").split("x")
            product_dims = tuple(float(p) for p in parts[:3])
            if len(product_dims) != 3 or any(d < 5 or d > 1000 for d in product_dims):
                raise ValueError("invalid")
        except (ValueError, IndexError):
            await message.answer(
                "Не понял формат. Напишите как: 220x90x85 или 'не знаю'."
            )
            return
    
    await state.update_data(product_dims=product_dims)
    await run_pipeline(message, state)


async def run_pipeline(message: Message, state: FSMContext):
    data = await state.get_data()
    
    await message.answer("⏳ Анализирую и проверяю размеры (10-15 сек)...")
    
    start_time = time.time()
    
    try:
        session_id = log_session(
            message.from_user.id,
            data["scene_url"], data["product_url"], data["target_class"],
            data.get("room_dims"), data.get("product_dims"),
            data.get("scene_qc"), data.get("product_qc"), None,
        )
        await state.update_data(session_id=session_id)
        
        result = await process_user_request(
            scene_url=data["scene_url"],
            product_url=data["product_url"],
            target_class=data["target_class"],
            room_dimensions_m=data.get("room_dims"),
            product_dims_cm=data.get("product_dims"),
            n_seeds=3,
            skip_quality_check=True,  # уже проверили в bot
            skip_size_check=(data.get("product_dims") is None),
        )
        
        # Размер не подходит
        if not result["success"] and result.get("error") == "size_mismatch":
            kb = InlineKeyboardBuilder()
            kb.button(text="✓ Делай как есть", callback_data="size_skip:yes")
            kb.button(text="❌ Отмена", callback_data="size_skip:no")
            
            sc = result["size_check"]
            await message.answer(
                f"⚠️ {result['message']}\n\n"
                f"Размер слота: ~{sc['slot_dims_cm']['width_cm']}×"
                f"{sc['slot_dims_cm']['height_cm']} см (confidence: {sc['slot_dims_cm']['confidence']})\n"
                f"Ваш товар: {data['product_dims'][0]}×{data['product_dims'][1]}×{data['product_dims'][2]} см\n"
                f"Отклонение: {sc['max_deviation']:.0f}%\n\n"
                f"Хотите всё равно сгенерировать?\n"
                f"(результат может выглядеть неестественно)",
                reply_markup=kb.as_markup(),
            )
            await state.set_state(GenStates.confirming_warning)
            return
        
        # Другие ошибки
        if not result["success"]:
            await message.answer(f"❌ {result.get('message', 'Ошибка')}")
            await state.clear()
            return
        
        duration = int(time.time() - start_time)
        gen_id = log_generation(session_id, result, duration)
        
        await send_result(message, result, gen_id, duration)
        
    except Exception as e:
        logging.exception("Pipeline failed")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")
    
    await state.clear()


@dp.callback_query(F.data.startswith("size_skip:"))
async def handle_size_skip(callback: CallbackQuery, state: FSMContext):
    _, choice = callback.data.split(":")
    
    if choice == "no":
        await callback.message.answer("Отменил. Команда /start чтобы начать заново.")
        await state.clear()
        return
    
    data = await state.get_data()
    await callback.message.answer("⏳ Делаю генерацию (45-60 сек)...")
    
    start_time = time.time()
    
    try:
        result = await process_user_request(
            scene_url=data["scene_url"],
            product_url=data["product_url"],
            target_class=data["target_class"],
            room_dimensions_m=data.get("room_dims"),
            product_dims_cm=data.get("product_dims"),
            n_seeds=3,
            skip_quality_check=True,
            skip_size_check=True,  # пропускаем т.к. пользователь уже видел warning
        )
        
        if not result["success"]:
            await callback.message.answer(f"❌ {result.get('message', 'Ошибка')}")
            await state.clear()
            return
        
        duration = int(time.time() - start_time)
        gen_id = log_generation(data["session_id"], result, duration)
        
        await send_result(callback.message, result, gen_id, duration, with_warning=True)
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)[:200]}")
    
    await state.clear()


async def send_result(message, result, gen_id, duration, with_warning=False):
    caption_lines = []
    if with_warning:
        caption_lines.append("⚠️ Сгенерировано с предупреждением о размере.")
    
    caption_lines.extend([
        f"✨ Готово! ({duration}с, ${result['cost']:.2f})",
        f"WOW: {result['validation']['wow_score']:.2f}/5",
        f"Visual identity: {result['validation']['catalog_sim']:.2f}",
        f"Presence: {result['validation']['presence_conf']:.2f}",
    ])
    
    if result.get("size_check"):
        caption_lines.append(
            f"Size match: {result['size_check']['max_deviation']:.0f}% deviation"
        )
    
    kb = rating_keyboard(gen_id)
    await message.answer_photo(
        result["url"],
        caption="\n".join(caption_lines),
        reply_markup=kb.as_markup(),
    )


def rating_keyboard(gen_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Отлично", callback_data=f"rate:{gen_id}:good")
    kb.button(text="😐 Средне", callback_data=f"rate:{gen_id}:mid")
    kb.button(text="👎 Плохо", callback_data=f"rate:{gen_id}:bad")
    return kb


@dp.callback_query(F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery):
    _, gen_id, rating = callback.data.split(":")
    update_user_rating(int(gen_id), rating)
    await callback.answer(f"Спасибо за оценку: {rating}")
    await callback.message.edit_caption(
        callback.message.caption + f"\n\n📊 Оценка: {rating}",
        reply_markup=None,
    )


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Implementation roadmap (день за днём)

### День 1: Скаффолд + базовый бот + БД

- [ ] Структура папок
- [ ] `pyproject.toml`, `.env.example`
- [ ] `db.py` со схемой users/sessions/generations
- [ ] `bot.py` с FSM states (без онбординга и quality check пока)
- [ ] `utils/storage.py` для 0x0.st
- [ ] `ai/preprocessing.py`
- [ ] Локальный запуск, базовый flow без AI

**Чек дня 1**: бот принимает данные через все шаги, пишет в БД.

### День 2: Quality Check + Scene Analysis

- [ ] `ai/quality_check.py` с двумя промптами
- [ ] `ai/scene_analysis.py` с GPT-5.4 Mini vision + GroundedSAM
- [ ] Интеграция quality check в bot.py с FSM-обработкой warn/reject
- [ ] Тест на 5-10 фото разного качества

**Чек дня 2**: бот корректно отклоняет не-интерьеры, предупреждает о тёмных фото.

### День 3: Pre-flight Size Check + Generation skeleton

- [ ] `ai/size_check.py` со всей геометрией
- [ ] `utils/geometry.py`
- [ ] Логика трёх кейсов (perfect/acceptable/marginal/doesnt_fit)
- [ ] Обработка кейса в bot.py с кнопками
- [ ] Скелет `ai/generation.py` (пока без best-of-N)
- [ ] Тест: один Fill Pro вызов end-to-end работает

**Чек дня 3**: бот отклоняет диван 350 см в 2.5-метровую комнату, генерит для нормальных кейсов.

### День 4: Best-of-N + Validation + Upscale

- [ ] Multi-seed (3 параллельных Fill Pro)
- [ ] `ai/validation.py` с CLIP-I, presence, SSIM
- [ ] WOW score формула
- [ ] Best-pick logic
- [ ] `ai/upscaling.py` Clarity Upscaler
- [ ] Полный pipeline end-to-end

**Чек дня 4**: бот возвращает best-of-3 с метриками за ~75 сек.

### День 5: Тестовый датасет + benchmark

- [ ] Собрать 30 inspiration-фото (10 easy / 15 medium / 5 hard)
- [ ] Собрать 20 catalog-фото с размерами в имени
- [ ] `scripts/benchmark.py` — прогон по датасету
- [ ] Сводная таблица результатов

**Чек дня 5**: получены реальные данные, видны failure cases.

### День 6: Подготовка визуальных assets для онбординга

⭐ **Этот день — ключевой для пилотирования**.

- [ ] Claude Code предлагает варианты для assets:
  - **Вариант A**: использовать готовые с Unsplash + добавить надписи в Pillow
  - **Вариант B**: сгенерировать через FLUX и GPT-5.4 Mini подобрать примеры
  - **Вариант C**: композит из реальных скриншотов в Figma
- [ ] **Скидывает на оценку пользователю**: «вот 3-4 варианта для каждой картинки, выбери»
- [ ] Создание/доводка финальных 4 ассетов в `assets/tutorial/`
- [ ] Реализация полного онбординга в bot.py
- [ ] `is_user_onboarded`, `mark_user_onboarded` в БД
- [ ] Команды `/start`, `/help`, `/cancel`

**Чек дня 6**: пройди туториал глазами свежего пользователя — понятно?

### День 7: Beta-тест + полировка

- [ ] Дать бота 3-5 знакомым дизайнерам и/или маркетологу Hoff/Divan
- [ ] Просить пройти по полному flow без подсказок
- [ ] Собрать обратную связь и оценки
- [ ] Финальная сводка: WOW score, success rate, user rating, cost

**Чек дня 7**: 30-50 живых регенераций, готово Go/No-go решение.

### День 8 (опционально): Tweaks по фидбэку

- [ ] Подгонка промптов под частые failure cases
- [ ] Возможно: добавить fallback на Kontext Pro для simple scenes (cheap path)
- [ ] Дополнительные tooltips в боте если что-то непонятно

---

## Готовая инструкция Claude Code: что делать в день 6 с assets

В день 6 **не нужно** Claude Code молча создавать assets. Нужно идти по протоколу:

```
Claude Code: 
"Сегодня день 6. Нужно собрать 4 визуальных asset для онбординга:
1. 01_intro.jpg — до/после
2. 02_scene_good_bad.jpg — примеры сцен ✅/❌
3. 03_product_good_bad.jpg — примеры товаров ✅/❌  
4. 04_size_help.jpg — как мерить размеры

У меня 3 варианта подхода:

A) Найти готовые примеры в интернете (Unsplash, Pinterest) 
   и собрать композиты в Pillow — самый быстрый, час работы.

B) Сгенерировать примеры через FLUX-1-schnell ($0.003 каждое),
   потом я подберу композиты — баланс между ручной работой и автоматикой.

C) Использовать твои реальные тестовые фото из data/test_inspirations/ 
   и собрать композиты с надписями — самый точный, но час работы.

Какой выбираешь? Или покажи примеры/собственные фото которые хочешь использовать."
```

Пользователь отвечает, дальше Claude Code:
1. Создаёт первую версию assets
2. Скидывает 4 файла на оценку через `present_files`
3. Ждёт фидбэка
4. При необходимости итерирует

**Не пропускай этот шаг** — ассеты должны быть нормальными, иначе онбординг не работает.

---

## Метрики и Go/No-go (без изменений от v2)

| Метрика | Easy target | Medium target | Hard target |
|---|---|---|---|
| WOW score | ≥3.8 | ≥3.3 | ≥2.5 |
| Success rate | ≥80% | ≥60% | ≥40% |
| Catalog fidelity | ≥0.78 | ≥0.72 | ≥0.65 |
| Size deviation max | ≤15% | ≤25% | ≤40% |
| User 👍 | ≥75% | ≥55% | ≥35% |
| Cost per gen | <$0.20 | <$0.30 | <$0.50 |
| Duration | <75s | <90s | <120s |

### Решение

| Условие | Решение |
|---|---|
| Все targets выполнены | ✅ **GO** — переход к PRODUCT_FULL.md |
| Easy ≥3.8, Medium 3.0-3.3, Hard <2.5 | ⚠️ **GO с ограничениями** — только гостиные/спальни |
| Catalog fidelity <0.65 | ⚠️ **PIVOT** — на матчинг без визуализации |
| Cost per success >$0.50 | ⚠️ **OPTIMIZE** — fallback на Kontext для simple scenes |
| Size deviation >25% даже при perfect-fit | ❌ **STOP** — нужен per-product LoRA |
| Easy <3.0 | ❌ **STOP** — фундаментальная проблема |
| **Quality check выявил >40% bad photos на тесте** | ⚠️ **IMPROVE** — улучшить онбординг и tooltips |
| **Onboarding completion rate <70%** | ⚠️ **IMPROVE** — упростить туториал |

---

## Edge cases (учесть в коде)

| Проблема | Решение |
|---|---|
| Quality check ложный reject (хорошее фото отклонено) | Логировать всё, потом анализировать |
| Quality check API падает | Fallback: skip QC, продолжить pipeline |
| Пользователь грузит фото 4K | Resize до 1280px по длинной стороне |
| Пользователь грузит несколько фото подряд | FSM игнорирует все кроме последнего в waiting_scene |
| GroundedSAM не находит объект | "Не вижу {target} в сцене" + предложение другой класс |
| 0x0.st temporary down | Fallback на imgbb или R2 |
| Replicate cold start | "Первый запуск, ожидание 60-90 сек" |
| Пользователь спамит регенерации | Лимит 5/день/user |
| Пользователь шлёт текст вместо фото | Подсказка "загрузите фото, не текст" |
| Размер не парсится (пользователь "три на четыре") | Просим переписать в формате "3x4" |

---

## Бюджет

| Расход | Сумма |
|---|---|
| Replicate (FLUX Fill Pro × 3 seeds + GroundedSAM + Clarity Upscaler + GroundingDINO + CLIP) | $150-220 |
| **OpenAI GPT-5.4 Mini** (quality check + scene analysis + product description) | $15-30 |
| Visual assets (если генерим через FLUX) | $1-3 |
| **Итого** | **$200-280** |

**Стоимость одного полного flow** (для понимания):

| Шаг | Модель | Цена |
|---|---|---|
| Scene quality check | GPT-5.4 Mini vision (low) | $0.002 |
| Product quality check | GPT-5.4 Mini vision (low) | $0.002 |
| Scene analysis | GPT-5.4 Mini vision (high) | $0.003 |
| GroundedSAM detection | Replicate | $0.005 |
| Product description | GPT-5.4 Mini vision (low) | $0.001 |
| FLUX Fill Pro × 3 | Replicate | $0.150 |
| Validation (CLIP × 2 + GroundingDINO + SSIM) | Replicate | $0.030 |
| Clarity Upscaler | Replicate | $0.016 |
| **Итого за успешный flow** | | **~$0.21** |

При 30-50 beta-тестах + 30 benchmark-сценах + ~30 итераций отладки = $200-250.

Если хочешь сэкономить ~$5-10 на тестах — переключи `OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-nano` (vision поддерживается, но менее точный для нюансов).

---

## Поехали

Перед стартом:

1. Зарегистрируйся в [replicate.com](https://replicate.com), пополни на $250
2. Создай Telegram-бота через [@BotFather](https://t.me/BotFather)
3. Зарегистрируйся в [platform.openai.com](https://platform.openai.com), пополни на $30
4. Подготовь датасет: 30 inspiration + 20 catalog-фото (час работы)
5. Установи Python 3.11+, [uv](https://docs.astral.sh/uv/)

Старт:

```bash
mkdir mvp-prototype && cd mvp-prototype
# Положи MVP_PROTOTYPE_v4.md
claude
> прочитай MVP_PROTOTYPE_v4.md и поехали с дня 1
```

День 6 — Claude Code остановится и спросит про visual assets. Это **обязательная синхронизация**, не пропускай.

Через 7-8 дней — фактический ответ на вопрос «работает или нет».

---

## Notes по работе с OpenAI API

1. **Версия SDK**: `pip install -U openai>=1.50.0`. В старых версиях нет поддержки GPT-5.4 семейства.

2. **Образы передаются по URL**, как и в Claude. Поскольку мы используем 0x0.st для temporary storage — URL публичный и доступен для OpenAI.

3. **`detail: "low"` vs `"high"`**: 
   - `low` = картинка ужимается до 512×512, ~85 input tokens, дешевле
   - `high` = детальная обработка, до 765 input tokens на «tile», дороже но точнее
   - Для quality check и product description хватает `low`
   - Для scene analysis (нужно считать ориентиры — двери, окна) — `high`

4. **`response_format={"type": "json_object"}`**: гарантирует валидный JSON в ответе. Не нужно writing parser с try/except — `json.loads()` работает напрямую. 

5. **Rate limits**: на free tier 3 RPM, на paid 500+ RPM. Для прототипа достаточно. Если упрёшься — используй экспоненциальный retry (есть в SDK через `max_retries`).

6. **Timeouts**: дефолт SDK 600 секунд, для нас норма (vision работает 1-3 сек).

7. **Async**: используй `AsyncOpenAI()`, не `OpenAI()`. В прототипе с aiogram это критично чтобы не блокировать event loop.

8. **Cost monitoring**: каждый запрос возвращает `response.usage.total_tokens` — логируй в БД для контроля бюджета.

9. **Гибрид для экономии**: если на бенчмарке выяснится что quality check работает не хуже на GPT-5.4 Nano — переключи `OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-nano` в .env. Экономия $0.003 за flow. Но **scene analysis и product description оставь на Mini** — они сложнее и Nano не «text-first worker» по доке.
