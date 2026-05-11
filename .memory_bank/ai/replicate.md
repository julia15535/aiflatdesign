# Replicate (FLUX, SAM, CLIP, GroundingDINO, Upscaler)

Используем Replicate для всех "тяжёлых" моделей: генерация изображений, сегментация, embedding, detection, upscale. Один API-ключ, один SDK.

## SDK

```
pip install replicate
```

API key через env `REPLICATE_API_TOKEN`. Получить — на https://replicate.com/account.

## Модели и зачем

| Stage | Модель | Что делает | Цена / call |
|---|---|---|---|
| 1 | `schananas/grounded_sam` | text-prompt segmentation (находит "sofa" в сцене → mask) | ~$0.005 |
| 3 | `black-forest-labs/flux-fill-pro` | inpainting в маску с учётом reference товара | ~$0.05 / seed |
| 4 | `adirik/grounding-dino` | detection (есть ли target_class в результате) | ~$0.005 |
| 4 | `andreasjansson/clip-features` | CLIP embeddings (для catalog fidelity) | ~$0.005 × 2 |
| 5 | `philz1337x/clarity-upscaler` | upscale 2× с сохранением деталей | ~$0.016 |

## Async-вызов

Все вызовы делаем через `replicate.async_run(...)` чтобы не блокировать aiogram event loop.

```python
import replicate
result = await replicate.async_run(
    "black-forest-labs/flux-fill-pro",
    input={
        "image": scene_url,
        "mask": mask_url,
        "prompt": "...",
        "guidance": 30,
        "num_inference_steps": 30,
        "safety_tolerance": 2,
        "output_format": "png",
        "seed": 42,
    },
)
url = result if isinstance(result, str) else result[0]
```

## GroundedSAM (Stage 1) — slot detection

```python
out = await replicate.async_run(
    "schananas/grounded_sam",
    input={
        "image": scene_url,
        "mask_prompt": target_class,  # "sofa", "bed", ...
        "negative_mask_prompt": "wall, floor, ceiling, window, door",
        "adjustment_factor": 12,
    },
)
# out: {masked_img, bbox, ...}
```

Если `out["masked_img"]` — None: слот не найден, fail с `no_slot_detected`.

## FLUX Fill Pro (Stage 3) — генерация

Параметры на основе benchmark:
- `guidance: 30` — высокий, чтобы результат был ближе к prompt и reference
- `num_inference_steps: 30` — sweet spot между качеством и временем
- `safety_tolerance: 2` — стандарт (1 строже, 6 либеральнее)
- `output_format: "png"` — без артефактов JPEG для validation
- `seed: 42 + i` — детерминированно для воспроизводимости, разные seeds для best-of-N

**Prompt структура** (см. `ai/prompts.md`):
```
"a {target_class} that matches the reference product exactly. "
"{product_description}. "
"{style} interior style, {lighting} lighting matching the room. "
"photorealistic, sharp focus, high detail, magazine-quality interior photography. "
"the {target_class} should fit naturally into the existing room geometry."
```

**Negative prompt** — единый константный для всех генераций:
```
"deformed, distorted, blurry, cartoon, oversaturated, plastic look, "
"fake, CGI, warped perspective, floating furniture, duplicated objects, "
"melting furniture, mismatched scale, watermark, text, logo, low quality"
```

## Grounding DINO (Stage 4) — presence

```python
detect = await replicate.async_run(
    "adirik/grounding-dino",
    input={
        "image": result_url,
        "query": target_class,
        "box_threshold": 0.30,
        "text_threshold": 0.25,
    },
)
# detect["detections"]: [{bbox, score}, ...]
presence_conf = max([d.get("score", 0) for d in detections] or [0])
```

## CLIP features (Stage 4) — catalog fidelity

```python
emb = await replicate.async_run("andreasjansson/clip-features", input={"inputs": result_url})
e = np.array(emb[0]["embedding"])
# Cosine similarity = catalog_sim
```

Делаем 2 раза (result + product reference) и считаем cosine.

## Clarity Upscaler (Stage 5) — polish

```python
out = await replicate.async_run(
    "philz1337x/clarity-upscaler",
    input={
        "image": image_url,
        "prompt": "masterpiece, best quality, photorealistic interior",
        "negative_prompt": "blurry, low quality, watermark, text",
        "scale_factor": 2,
        "creativity": 0.35,   # больше — больше "доделок", может изменить детали
        "resemblance": 0.6,   # высокое — сохраняет оригинал
        "num_inference_steps": 18,
    },
)
```

Применяем **только** если `validation.passed = True` — иначе тратим деньги на плохую картинку.

## Cold start

Replicate-модели могут "просыпаться" 60-90 сек если давно не вызывались. Для MVP это редко, но если случилось — пользователь видит "первый запуск, ожидание...".

## Параллельность

3 seeds Fill Pro можно запускать через `asyncio.gather` — Replicate держит concurrent requests.

```python
results = await asyncio.gather(*[
    generate_with_fill_pro(..., seed=42 + i) for i in range(3)
])
```

Watch out: на free tier есть concurrent limit. На paid — норм.

## Стоимость в одном flow

| Шаг | Модель | Цена |
|---|---|---|
| Slot detection | GroundedSAM | $0.005 |
| Generation × 3 | FLUX Fill Pro | $0.15 |
| Validation (CLIP × 2 + DINO + SSIM) | mix | $0.030 |
| Upscale (опц.) | Clarity | $0.016 |
| **Итого Replicate часть** | | **$0.20** |
