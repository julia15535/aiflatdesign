# Stage 2: Pre-flight Size Check

Алгоритмическая проверка (без AI) — вписывается ли товар в слот по реальным размерам. Не блокирует pipeline жёстко: при marginal/doesnt_fit предлагает пользователю выбор.

## Входы / выходы

```python
def estimate_slot_dimensions(
    bbox: list,                       # [x1, y1, x2, y2] в px
    scene_image_url: str,
    room_dimensions_m: tuple = None,  # (5.0, 4.0)
    scene_analysis: dict = None,      # для room_type fallback и scale_references
) -> dict:
    # → {width_cm, height_cm, depth_cm, confidence: "high|medium|low", bbox_px}

def check_fit(
    product_dims_cm: tuple,           # (длина, глубина, высота) в см
    slot_dims: dict,
    tolerance_pct: int = 15,
) -> dict:
    # → {fits, deviation_pct: {...}, max_deviation, verdict, explanation,
    #    slot_dims_cm, product_dims_cm}
```

## Алгоритм оценки слота

3 ветки в порядке убывания точности:

### 1. Пользователь дал room_dimensions_m

```
scene_width_m = max(room_dimensions_m) * 0.75    # 75% длинной стены попадает в кадр
m_per_px = scene_width_m / img_width
slot_width_cm  = bbox_w_px * m_per_px * 100
slot_height_cm = bbox_h_px * m_per_px * 100
slot_depth_cm  = slot_width_cm * 0.5             # эвристика
confidence = "high"
```

### 2. Есть `scale_references` из Scene Analysis

Использует упоминания "door visible" (200 см) или "window with sill" (80 см) как референс. В прототипе упрощено — берём `scene_width_m = 4.5` как default. В production детектируем дверь/окно через GroundedSAM.

`confidence = "medium"`

### 3. Только room_type из Scene Analysis

```python
room_type_defaults = {
    "living_room": (5.0, 4.0),
    "bedroom": (4.0, 3.5),
    "kitchen": (4.0, 3.0),
    "bathroom": (2.5, 2.0),
    "office": (4.0, 3.0),
}
long, _ = room_type_defaults.get(room_type, (4.5, 3.5))
scene_width_m = long * 0.75
```

`confidence = "low"`

## check_fit — вердикты

```python
max_abs_dev = max(abs(d) for d in deviations.values())   # % deviation по width/height/depth

if max_abs_dev <= tolerance_pct (15):          verdict = "perfect"     fits=True
elif max_abs_dev <= tolerance_pct * 2 (30):    verdict = "acceptable"  fits=True
elif max_abs_dev <= tolerance_pct * 3 (45):    verdict = "marginal"    fits=False
else:                                          verdict = "doesnt_fit"  fits=False
```

## Что делает pipeline

```python
if size_check_result["verdict"] in ["doesnt_fit", "marginal"]:
    return {"success": False, "error": "size_mismatch", ...}
```

В бот flow это:
- Показывает explanation + slot_dims + product_dims
- Кнопки: `[✓ Делай как есть]` (повторный pipeline с `skip_size_check=True`) или `[❌ Отмена]`

## Edge cases

| Случай | Что делаем |
|---|---|
| `product_dims_cm = None` | Stage 2 пропускается (`skip_size_check=True`). В bot flow дальше идёт без проверки |
| `room_dimensions_m = None`, есть scene_analysis | Идём по ветке 2 или 3, confidence = medium/low |
| `bbox` нулевого размера | Не должно случаться (GroundedSAM не вернёт found=True для пустого bbox), но защищаемся: проверяем `bbox_w_px > 0 and bbox_h_px > 0` |
| Wide-angle perspective | `confidence` снижаем на ступень — известно что искажает размеры |

## Тесты

- Диван 350x110x90 см в спальне 4x3 м — ожидаем `doesnt_fit` (слишком большой)
- Диван 220x90x85 см в гостиной 5x4 м — ожидаем `perfect` (когда room_dims даны)
- Лампа 30x30x150 в любой комнате — ожидаем `acceptable` (маленький объект, толерантнее)

## Известное ограничение MVP

Алгоритм даёт **оценку**, не точную меру. Реальные размеры зависят от угла съёмки, высоты камеры. Поэтому:
- `tolerance_pct = 15` по умолчанию — даём запас.
- `confidence` присутствует в результате — поможет интерпретировать ошибки.
- Пользователь всегда может сказать "всё равно делай".

В production: использовать MiDaS depth estimation для более точной оценки.
