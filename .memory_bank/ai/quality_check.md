# Stage 0: Photo Quality Check

Сразу после загрузки фото — проверка качества через GPT-5.4 Mini vision. Спасает от "мусорных" входов (не интерьер, тёмные фото, скриншоты с маркетплейса).

## Зачем

Без QC pipeline бы запустил Fill Pro на любом мусоре и сжёг $0.20 на бесполезный результат. QC стоит $0.002 за проверку — экономит $0.20 при каждом отклонении.

## Контракт

```python
async def check_scene_quality(image_url: str) -> dict:
    # → {is_interior_photo, quality_score, lighting, resolution_adequate, perspective,
    #    issues: [...], recommendation: "proceed" | "warn_user" | "reject", user_message}

async def check_product_quality(image_url: str) -> dict:
    # → {is_furniture_photo, is_catalog_style, quality_score, single_item_visible,
    #    fully_visible, background_complexity, has_watermark_or_text,
    #    issues: [...], recommendation, user_message}
```

Промпты — в `ai/prompts.md`.

## Логика recommendation

| recommendation | Что делает бот |
|---|---|
| `proceed` | Молча переходит к следующему шагу |
| `warn_user` | Показывает `user_message` + кнопки `[✓ Всё равно делать]` `[↻ Загрузить другое]` |
| `reject` | Показывает `user_message` + просит другое фото; state не меняется |

## Когда `reject`

- Сцена: фото не интерьера (улица, портрет, документ, скриншот рабочего стола)
- Товар: не мебель и не декор (одежда, машина, еда, документ)

## Когда `warn_user`

- Сцена: очень тёмное / искажение от рыбьего глаза / только угол комнаты
- Товар: несколько предметов в кадре / водяной знак / ценник / только часть товара видна

## Edge cases

| Случай | Поведение |
|---|---|
| QC API падает (timeout/500) | Логируем, `recommendation = "proceed"` (не блокируем) |
| Картинка > 4K | Используем `detail: "low"` — Mini сама ужмёт до 512×512 |
| Фото настолько хорошее что AI всё равно говорит warn | Опираемся на `recommendation`, не на отдельные флаги |
| Фото в плохом качестве, но пользователь жмёт "Всё равно делать" | Идёт в pipeline; warning остаётся в `result.warnings` |

## Логирование

В `sessions.scene_quality_json` и `sessions.product_quality_json` — **полный** ответ QC. Это нужно для:
- Анализа ложных reject'ов после первой партии beta-тестов
- Подгонки prompt'а если QC слишком строгий или слишком мягкий

## Стоимость

- `detail: low` → 85 input tokens + ~150 output tokens
- На GPT-5.4 Mini: ~$0.00015 input + ~$0.00067 output = **~$0.002 на проверку**
- В flow: scene QC + product QC = $0.004

При переключении на `gpt-5.4-nano`:
- $0.20/$1.25 за 1M tokens → ~$0.0007 на проверку (3× дешевле)
- Менее точный — может пропустить плохое фото или ложно отклонить хорошее
- Если на бенчмарке оба фейлят одинаково — переключаем `OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-nano`

## Тесты на день 2

Прогнать через QC:
- 5 нормальных фото комнат
- 2 не-интерьера (улица, портрет)
- 2 тёмных фото
- 5 нормальных фото товаров
- 2 скриншота с ценником
- 2 фото с несколькими предметами

Ожидание: 90%+ корректных классификаций (proceed/warn/reject).
