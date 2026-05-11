# Domain: Pipeline (Stage 0-5)

Конвейер обработки одного запроса: фото сцены + фото товара + target_class + (опционально размеры) → готовая картинка с вписанным товаром + метрики.

## Stage'и

| # | Что делает | Технология | Время | Цена / call |
|---|---|---|---|---|
| 0 | Quality check сцены и товара | GPT-5.4 Mini vision (low) | ~3 сек | ~$0.004 |
| 1 | Scene Analysis + Slot detection | GPT-5.4 Mini vision (high) + GroundedSAM | ~10-15 сек | ~$0.008 |
| 2 | Pre-flight Size Check | алгоритм (bbox + room dims) | <1 сек | $0 |
| 3 | Generation × 3 seeds | FLUX Fill Pro | ~45-60 сек | ~$0.150 |
| 4 | Validation | CLIP-I × 2 + Grounding DINO + SSIM | ~10 сек | ~$0.030 |
| 5 | Polish (опц.) | Clarity Upscaler 2× | ~10 сек | ~$0.016 |
| | + Product description | GPT-5.4 Mini vision (low) | ~2 сек | ~$0.001 |
| | **Итого успешный flow** | | **~75-90 сек** | **~$0.21** |

## Контракт `process_user_request`

```python
async def process_user_request(
    scene_url: str,
    product_url: str,
    target_class: str,
    room_dimensions_m: tuple = None,
    product_dims_cm: tuple = None,
    n_seeds: int = 3,
    skip_quality_check: bool = False,
    skip_size_check: bool = False,
) -> dict
```

Возвращает:

| Поле | Описание |
|---|---|
| `success: bool` | True если всё OK, False если упало на любом stage'е |
| `url: str` | URL итоговой картинки (если success) |
| `variants: list[str]` | URL'ы топ-3 кандидатов (best-of-N) |
| `validation: dict` | `{wow_score, catalog_sim, presence_conf, ssim_score, aesthetic, position_ok}` |
| `size_check: dict | None` | результат Stage 2 (если product_dims_cm заданы) |
| `scene_analysis: dict` | вывод Stage 1 |
| `cost: float` | накопленная стоимость в USD |
| `warnings: list` | предупреждения из quality check (если recommendation=warn_user) |
| `error: str | None` | код ошибки если success=False (`scene_rejected`, `product_rejected`, `no_slot_detected`, `size_mismatch`, `all_seeds_failed`) |
| `message: str | None` | человекочитаемое сообщение для пользователя |

## Ранние выходы (фейлы)

Из любого stage'а pipeline может вернуть `{"success": False, "error": ..., "message": ...}`:

| `error` | Когда | Что показать пользователю |
|---|---|---|
| `scene_rejected` | QC сцены: recommendation=reject | "Это не похоже на фото интерьера" |
| `product_rejected` | QC товара: recommendation=reject | "Это не похоже на фото мебели/товара" |
| `no_slot_detected` | GroundedSAM не нашёл target_class | "Не вижу подходящего места для {target_class}" |
| `size_mismatch` | check_fit: verdict in [marginal, doesnt_fit] | Предложить "Всё равно делать" или загрузить другой товар |
| `all_seeds_failed` | Все 3 Fill Pro вызова упали | "Не удалось сгенерировать" + retry |

## WOW score (Stage 4)

```
wow_score = (
    catalog_sim * 0.4 +
    (presence_conf if presence_conf >= 0.4 else 0) * 0.3 +
    (aesthetic / 10) * 0.2 +
    (ssim_score if ssim_score >= 0.7 else 0) * 0.1
) * 5
```

Картинка `passed`, если выполнены ВСЕ:
- `presence_conf >= 0.4` (Grounding DINO видит target в результате)
- `catalog_sim >= 0.65` (CLIP-I result ↔ product)
- `ssim_score >= 0.70` (структура сцены сохранена)
- `position_ok` (IoU bbox detected ↔ slot > 0.3)

## Optimization knobs

| Хотим | Меняем |
|---|---|
| Дешевле QC | `OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-nano` (экономия ~$0.003/flow) |
| Меньше вариантов | `n_seeds=1` (экономия ~$0.10/flow, но ниже шанс хорошего результата) |
| Без upscale | `passed=False` пропускает Stage 5 автоматически; можно отключить совсем |
| Без size check | `skip_size_check=True` если `product_dims_cm` не заданы |

## См. также

- `ai/quality_check.md` — детали Stage 0
- `ai/scene_analysis.md` — детали Stage 1
- `ai/size_check.md` — детали Stage 2
- `ai/generation.md` — детали Stage 3
- `ai/validation.md` — детали Stage 4 и WOW score
- `ai/upscaling.md` — детали Stage 5
