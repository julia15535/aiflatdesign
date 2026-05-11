# Stage 5: Optional Polish (Clarity Upscaler)

Финальный upscale 2× с сохранением деталей. Опциональный — применяется **только** если кандидат прошёл валидацию (`passed=True`).

## Зачем

FLUX Fill Pro выдаёт 1024×1024 или меньше. Для маркетинговых картинок (лендинги, соцсети) хочется 2048×2048. Clarity Upscaler делает это с сохранением структуры и без артефактов.

## Когда применяем

```python
if best_val["passed"]:
    try:
        best_url = await upscale_final(best_url, scale=2)
        cost_estimate += 0.016
    except Exception as e:
        logger.warning(f"Upscale failed, skipping: {e}")
        # Не блокируем — отдаём не-upscaled
```

Если `passed=False` — пропускаем (бессмысленно "полировать" плохой результат).

## Параметры

```python
out = await replicate.async_run(
    "philz1337x/clarity-upscaler",
    input={
        "image": image_url,
        "prompt": "masterpiece, best quality, photorealistic interior",
        "negative_prompt": "blurry, low quality, watermark, text",
        "scale_factor": 2,
        "creativity": 0.35,
        "resemblance": 0.6,
        "num_inference_steps": 18,
    },
)
```

| Параметр | Значение | Что делает |
|---|---|---|
| `scale_factor: 2` | 2× | Удваивает разрешение |
| `creativity: 0.35` | низкое | Минимальные изменения деталей |
| `resemblance: 0.6` | среднее | Сохраняет оригинал |
| `num_inference_steps: 18` | sweet spot | Меньше → артефакты; больше → дольше |

## Failure handling

Если Clarity упал (cold start timeout, model removed, etc) — **не падаем**. Логируем warning, возвращаем не-upscaled URL. Пользователь получает более низкое разрешение, но рабочий результат.

## Стоимость

~$0.016 / call. Применяется только к passed-кандидатам (~50-70% от всех). Эффективная стоимость в среднем: $0.008 на flow.

## Время

~10 сек на 2× upscale.

## Полный объём затрат

Если для всех flows passed=True → 100% upscale → $0.016/flow добавляется. Если passed=False — экономим.

## Альтернативы (если нужно дешевле)

- `nightmareai/real-esrgan` ($0.001/call, проще, без AI коррекции) — для bench-mode выкладок
- `philz1337x/upscale-an-image-with-clarity-upscaler` — тот же, более новые ноды

## Edge cases

| Случай | Поведение |
|---|---|
| Upscale меняет цвет/обивку | Снижаем `creativity` до 0.25, повышаем `resemblance` до 0.75 |
| Upscale "выглаживает" текстуры | Поднимаем `num_inference_steps` до 25 |
| Timeout > 30 сек | Считаем за fail, отдаём не-upscaled с warning'ом в логах |
