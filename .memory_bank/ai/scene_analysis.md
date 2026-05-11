# Stage 1: Scene Analysis + Slot Detection

Параллельно: (1) Vision-анализ сцены через GPT-5.4 Mini high-detail, (2) Поиск слота под target_class через GroundedSAM.

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
