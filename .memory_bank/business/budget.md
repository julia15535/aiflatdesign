# Бюджет MVP

Целевой потолок: **$200-280** на 6-8 дней разработки + бенчмарк + beta-тесты.

## Разбивка

| Категория | Сумма |
|---|---|
| Replicate (FLUX × 3 + GroundedSAM + Clarity + GroundingDINO + CLIP) | $150-220 |
| OpenAI GPT-5.4 Mini (QC × 2 + scene + product description) | $15-30 |
| Visual assets для онбординга (если генерим FLUX'ом) | $1-3 |
| **Итого** | **$200-280** |

Сервер 193.160.208.41 уже работает — отдельной платы нет.

## Стоимость одного flow (для понимания unit-экономики)

| Шаг | Модель | Цена |
|---|---|---|
| Scene quality check | GPT-5.4 Mini (low) | $0.002 |
| Product quality check | GPT-5.4 Mini (low) | $0.002 |
| Scene analysis | GPT-5.4 Mini (high) | $0.003 |
| GroundedSAM detection | Replicate | $0.005 |
| Product description | GPT-5.4 Mini (low) | $0.001 |
| FLUX Fill Pro × 3 seeds | Replicate | $0.150 |
| Validation (CLIP × 2 + DINO + SSIM) | Replicate | $0.030 |
| Clarity Upscaler (опционально, если passed) | Replicate | $0.016 |
| **Итого успешный flow** | | **~$0.21** |

## Прогноз по MVP

| Активность | Количество | Стоимость |
|---|---|---|
| Дебаг и итерации (дни 1-4) | ~30 flow'ов | $7 |
| Benchmark (день 5) | 30 inspirations × 20 catalog = 600 потенциальных flow'ов | до $130 |
| Beta-тест (день 7) | 30-50 живых регенов | $10 |
| Buffer | | $50 |
| **Итого** | | **~$200** |

Реалистично — большую часть тестов делаем подгруппами (10-15 sample flows на основные failure modes), не 600.

## Где можно сэкономить

1. **`OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-nano`** — экономия ~$0.003/flow на quality check. На 1000 flow'ах = $3.
2. **`n_seeds=2` вместо 3** — экономия $0.05/flow, но падает best-pick рейт.
3. **Skip upscale при passed=False** — уже в коде, экономия $0.016 на каждом fail-кейсе.
4. **Меньше тест-сцен** — вместо 30 inspirations × 20 catalog взять 10 × 5 = 50 тестов.

## Где НЕ экономим

1. ❌ Scene analysis на nano — ломает детекцию ориентиров (door, window).
2. ❌ `num_inference_steps < 20` в Fill Pro — выпадают артефакты.
3. ❌ Skip Quality Check глобально — теряем early reject ($0.20/flow на мусоре).

## Контроль расходов

В коде:
```python
if total_cost > float(os.environ.get("COST_LIMIT_USD", "300")):
    raise RuntimeError(f"Cost limit exceeded: ${total_cost}")
```

В дашбордах:
- OpenAI: https://platform.openai.com/usage
- Replicate: https://replicate.com/account/billing

В БД:
```sql
SELECT SUM(cost_usd) FROM generations WHERE created_at >= datetime('now', '-7 days');
```

Запускаем ежедневно глазами или в `scripts/eval_results.py`.

## После Go-решения

Если переходим к продуктизации (PRODUCT_FULL):
- Бюджет вырастает кратно (10× на pilot с одним ритейлером)
- Нужны: Cloudflare R2 (~$10/мес), Sentry, аналитика, payment processor
- Сервер: dedicated VPS (~$20/мес) или Kubernetes namespace

Сейчас не планируем.
