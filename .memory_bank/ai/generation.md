# Stage 3: Generation (FLUX Fill Pro × N seeds)

Inpainting в маску слота с учётом фото товара (reference). Делаем `N=3` seeds, дальше Stage 4 валидирует и выбирает best.

## Шаги

### 1. Описание товара (vision)

```python
async def describe_product(product_url: str) -> str:
    # GPT-5.4 Mini vision (low detail)
    # → 50-60 слов английского описания товара
```

Промпт: "Опиши этот предмет мебели для AI image generation prompt. Включи: тип, цвет, материал/обивку, узор/паттерн, форму, стиль ножек/основания, особые детали. Кратко, до 60 слов, на английском, без preamble."

### 2. Сборка prompt'а

```
"a {target_class} that matches the reference product exactly. "
"{product_description}. "
"{style} interior style, {lighting} lighting matching the room. "
"photorealistic, sharp focus, high detail, magazine-quality interior photography. "
"the {target_class} should fit naturally into the existing room geometry."
```

`{style}` и `{lighting}` берутся из `scene_analysis`. Если их нет — defaults (`modern`, `natural_daylight`).

### 3. Fill Pro вызовы

`N=3` параллельных вызовов с разными seeds (42, 43, 44). Каждый стоит ~$0.05.

Параметры:
- `image: scene_url`
- `mask: mask_url` (из GroundedSAM)
- `prompt: <собранный>`
- `guidance: 30`
- `num_inference_steps: 30`
- `safety_tolerance: 2`
- `output_format: "png"`
- `seed: 42+i`

```python
candidates = []
for i in range(n_seeds):
    try:
        gen = await generate_with_fill_pro(scene_url, mask_url, product_url,
                                            target_class, product_desc, scene_analysis,
                                            seed=42 + i)
        v = await validate_result(gen, target_class, product_url, scene_url,
                                   slot_bbox=slot_detection["bbox"])
        candidates.append((v["wow_score"], gen, v))
    except Exception as e:
        logger.error(f"Generation failed seed={i}: {e}")
        continue
```

⚠️ Если все 3 seeds упали — fail с `all_seeds_failed`.

### 4. Best-pick

```python
candidates.sort(reverse=True, key=lambda x: x[0])
_, best_url, best_val = candidates[0]
variants = [c[1] for c in candidates[:3]]   # для логирования и UI
```

## Параллелизм

3 seeds должны идти через `asyncio.gather`, иначе общее время = 3 × 50 сек = 150 сек. С параллельностью — 50-60 сек.

Замечание: код выше показан последовательным. **Реализуем** параллельным через `asyncio.gather([generate+validate task] for each seed)`.

## Reference товара

⚠️ **FLUX Fill Pro в текущей версии не принимает product_url как reference напрямую.** В оригинальном коде MVP `product_url` принимается как параметр, но дальше передаётся **только** в prompt'е через текст `product_description`. Это сознательное решение:
- Описание через vision Mini даёт более стабильный результат
- Не требует FLUX Redux / IP-Adapter
- Снижает variance

Если в день 4 на бенчмарке окажется что catalog_sim < 0.65 — добавить FLUX Redux (image-to-image conditioning) или IP-Adapter.

## Negative prompt

Константный, не зависит от сцены/товара:

```
"deformed, distorted, blurry, cartoon, oversaturated, plastic look, "
"fake, CGI, warped perspective, floating furniture, duplicated objects, "
"melting furniture, mismatched scale, watermark, text, logo, low quality"
```

## Стоимость

- Product description: $0.001
- Fill Pro × 3: $0.15
- **Итого Stage 3**: $0.151

## Время

- Описание товара (Mini low): ~2 сек
- 3 Fill Pro параллельно: ~50-60 сек
- **Итого Stage 3**: ~55-65 сек

## Edge cases

| Случай | Поведение |
|---|---|
| Replicate cold start (FLUX давно не использовался) | Первый seed может занять 90 сек. Логируем. Бот показывает "Первый запуск, ждём..." |
| 1 из 3 seeds упал | Берём best из оставшихся 2 |
| Все 3 упали | `error: "all_seeds_failed"` + retry-кнопка в боте |
| Concurrent limit Replicate | Снижаем до `n_seeds=2` через env (`REPLICATE_PARALLEL_SEEDS`) |
