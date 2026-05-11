# Stage 1: Scene Analysis + Slot Detection

В **Шаге 2.5** (pre-flight check) реализована **упрощённая** версия — только оценка размеров слота через OpenAI vision **без** GroundedSAM. Точная маска через GroundedSAM добавится в Шаге 3.

## Шаг 2.5: estimate_slot_dimensions (упрощённая версия)

Файл: `ai/scene_analysis.py`

```python
async def estimate_slot_dimensions(
    scene_url: str,
    target_en: str,        # "dining table"
    target_ru: str,        # "обеденный стол"
    ceiling_cm: int,       # 270
    room_description: str, # "Часть гостиной 18м²"
) -> dict
```

Возвращает:
```json
{
  "scale_references": ["window ~150cm высота", "radiator ~60cm", ...],
  "estimated_slot": {"width_cm": 140, "depth_cm": 90, "height_cm": 76},
  "confidence": "low | medium | high",
  "reasoning": "у эркера обычно ставят обеденный стол 120-140см...",
  "warnings": ["комната видна только частично"],
  "is_target_appropriate_for_room": true,
  "appropriate_explanation": ""
}
```

**Промпт**: `SLOT_ESTIMATION` в `ai/prompts.py`. Использует:
- Высоту потолка как масштабную линейку
- Описание комнаты как контекст
- Английское название объекта для понимания типичных размеров

**Detail**: `high` — критично видеть мелкие референсы (плинтус, розетки, сиденья стульев).

**Fallback**: при ошибке API / неверном JSON / некорректных размерах — возвращаем дефолтные размеры для типа объекта (см. `_DEFAULT_SLOTS`) + `confidence=low` + `_fallback=true`.

## Полная версия (Шаг 3)

В Шаге 3 параллельно к `estimate_slot_dimensions` будет работать GroundedSAM:

```python
async def detect_target_slot(image_url: str, target_class: str) -> dict:
    # → {mask_url, bbox, found}
```

И `analyze_scene(image_url)` через OpenAI — для определения стиля/освещения/сцены (понадобится для генерационного промпта FLUX).



## Vision-анализ сцены

```python
async def analyze_scene(image_url: str) -> dict:
    # → {room_type, perspective, lighting, style, existing_objects, estimated_room_area_sqm,
    #    wall_color, floor_type, scale_references: [...], complexity, issues: [...]}
```

Промпт — в `ai/prompts.md` (`CLAUDE_SCENE_PROMPT`).

Поля JSON:

| Поле | Значения | Зачем |
|---|---|---|
| `room_type` | `living_room`, `bedroom`, `kitchen`, `bathroom`, `office`, `hallway`, `other` | Если размеры неизвестны — берём defaults по типу комнаты |
| `perspective` | `wide_angle`, `normal`, `tight` | Wide-angle искажает размеры — снижаем confidence в Stage 2 |
| `lighting` | `natural_daylight`, `evening`, `artificial`, `mixed` | В prompt'е генерации |
| `style` | `modern`, `scandinavian`, `classic`, `loft`, `minimalist`, `other` | В prompt'е генерации |
| `existing_objects` | список | Информативно (не используем напрямую) |
| `estimated_room_area_sqm` | int | Информативно |
| `wall_color`, `floor_type` | вариант из перечня | В prompt'е генерации |
| `scale_references` | список строк типа "door visible (assumed 200cm tall)" | Helper для Stage 2 если размеры не заданы |
| `complexity` | `easy`, `medium`, `hard` | Для benchmark'а — категоризация результатов |

`detail: "high"` — нам нужно увидеть ориентиры (двери, окна, плинтус) для оценки масштаба.

## Slot detection (GroundedSAM)

```python
async def detect_target_slot(image_url: str, target_class: str) -> dict:
    out = await replicate.async_run(
        "schananas/grounded_sam",
        input={
            "image": image_url,
            "mask_prompt": target_class,                                # "sofa", "bed", ...
            "negative_mask_prompt": "wall, floor, ceiling, window, door",
            "adjustment_factor": 12,
        },
    )
    return {"mask_url": out.get("masked_img"), "bbox": out.get("bbox"), "found": ...}
```

Возвращает:
- `mask_url` — белая маска на чёрном фоне (для Fill Pro)
- `bbox` — `[x1, y1, x2, y2]` в пикселях
- `found` — bool, есть ли слот вообще

Если `found = False` — fail с `no_slot_detected`. Пользователь видит "Не вижу подходящего места для {target_class}".

## adjustment_factor

`12` — расширяет mask на N пикселей. Меньше — рискуем обрезать товар в результате. Больше — Fill Pro трогает соседние объекты. `12` — sweet spot из бенчмарка автора схемы.

## Параллельность

`analyze_scene` (OpenAI) и `detect_target_slot` (Replicate) **можно** запустить параллельно через `asyncio.gather`. Экономия ~5-7 сек на flow.

```python
scene_analysis, slot_detection = await asyncio.gather(
    analyze_scene(scene_url),
    detect_target_slot(scene_url, target_class),
)
```

## Что отдаём дальше

В Stage 2 и Stage 3 идут:
- `scene_analysis` — для prompt'а генерации (style, lighting) и оценки размеров (room_type defaults, scale_references)
- `slot_detection.mask_url` — на вход Fill Pro
- `slot_detection.bbox` — на вход size_check.estimate_slot_dimensions

## Стоимость

- Scene analysis: ~$0.003 (high detail, 765 input tokens на tile + ~500 output)
- Slot detection: ~$0.005 (GroundedSAM)
- **Итого Stage 1**: ~$0.008
