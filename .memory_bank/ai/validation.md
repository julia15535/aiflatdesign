# Stage 4: Validation (CLIP-I + Grounding DINO + SSIM + WOW score)

4 метрики, агрегированные в WOW score. Используется для (1) выбора best-of-N, (2) `passed` флага → решения upscale'ить или нет, (3) показа метрик пользователю.

## Метрики

### 1. Presence (Grounding DINO)

Видит ли в результате target_class?

```python
detect = await replicate.async_run("adirik/grounding-dino", input={
    "image": result_url, "query": target_class,
    "box_threshold": 0.30, "text_threshold": 0.25,
})
detections = detect.get("detections", [])
presence_conf = max([d.get("score", 0) for d in detections] or [0])
```

`presence_conf ∈ [0, 1]`. Хорошо: ≥ 0.4.

### 2. Position check (IoU)

Bbox detected target пересекается с bbox исходного слота?

```python
if slot_bbox and detections:
    ious = [compute_iou(d["bbox"], slot_bbox) for d in detections]
    position_ok = max(ious) > 0.3 if ious else False
```

Если `position_ok = False` — товар появился в неправильном месте сцены.

### 3. Catalog fidelity (CLIP-I)

Похож ли товар в результате на reference из каталога?

```python
emb_result = await replicate.async_run("andreasjansson/clip-features", input={"inputs": result_url})
emb_product = await replicate.async_run("andreasjansson/clip-features", input={"inputs": product_url})
e1 = np.array(emb_result[0]["embedding"])
e2 = np.array(emb_product[0]["embedding"])
catalog_sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))
```

`catalog_sim ∈ [-1, 1]`. Хорошо: ≥ 0.65.

⚠️ CLIP-I сравнивает **всю** картинку, не вырезанный товар. Это даст shifted baseline (общий фон, освещение могут поднять метрику). Для MVP — приемлемо; для production — вырезать товар по bbox и сравнивать только его.

### 4. Scene preservation (SSIM)

Не сломалась ли структура сцены вне области инпейнтинга?

```python
img_orig = np.array(Image.open(BytesIO(requests.get(scene_url).content)).convert("L"))
img_result = np.array(Image.open(BytesIO(requests.get(result_url).content)).convert("L"))
if img_orig.shape != img_result.shape:
    img_result = np.array(Image.fromarray(img_result).resize(img_orig.shape[::-1]))
ssim_score = float(ssim(img_orig, img_result, data_range=255))
```

`ssim_score ∈ [0, 1]`. Хорошо: ≥ 0.70.

⚠️ SSIM считается по всему изображению — включая инпейнт область, где он *должен* отличаться от оригинала. На MVP это компромисс; идеально — mask-aware SSIM (вне маски считаем).

### 5. Aesthetic (placeholder)

В коде MVP это `5.0` (фиксированное). В production — заменить на real aesthetic scorer (LAION).

## WOW score

```
wow_score = (
    catalog_sim * 0.4 +
    (presence_conf if presence_conf >= 0.4 else 0) * 0.3 +
    (aesthetic / 10) * 0.2 +
    (ssim_score if ssim_score >= 0.7 else 0) * 0.1
) * 5
```

Веса (catalog 40 / presence 30 / aesthetic 20 / ssim 10) — отражают приоритет: **визуальная идентичность товара важнее всего**.

`wow_score ∈ [0, 5]`.

## Passed флаг

```python
passed = (
    presence_conf >= 0.4 and
    catalog_sim >= 0.65 and
    ssim_score >= 0.70 and
    position_ok
)
```

Все 4 пороги — конъюнкция. Используется для:
- Solo решения upscale'ить (`if passed: upscale_final(...)`)
- Анализа: % passed vs %  not passed

## Параллельность

CLIP × 2 + Grounding DINO + SSIM (локальный numpy) можно делать параллельно:

```python
detect_task, emb_r_task, emb_p_task = await asyncio.gather(
    grounding_dino_call(result_url, target_class),
    clip_features(result_url),
    clip_features(product_url),
)
ssim_score = compute_ssim_locally(scene_url, result_url)   # после await'ов
```

## Стоимость

- Grounding DINO: ~$0.005
- CLIP features × 2: ~$0.010
- SSIM: $0 (локально)
- **Итого Stage 4**: ~$0.030 на 1 кандидата
- При 3 seeds: ~$0.090 на всё валидирование

## Что вернуть в pipeline

```python
return {
    "passed": bool,
    "presence_conf": float,
    "catalog_sim": float,
    "ssim_score": float,
    "aesthetic": float,
    "position_ok": bool,
    "wow_score": float,
}
```

## Edge cases

| Случай | Поведение |
|---|---|
| Detections пустые → presence_conf = 0 | wow_score автоматически снижается за счёт `<0.4` штрафа |
| CLIP API возвращает разные размеры embedding'ов (бывает если apex модели поменялись) | Логируем и берём как есть — np.dot всё равно сработает |
| Result image не загрузился (404 на 0x0.st) | Skip кандидата, идём дальше |
| Все 3 кандидата not passed | Берём best по wow_score, upscale пропускаем |
