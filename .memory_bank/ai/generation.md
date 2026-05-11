# Stage 3: Generation через OpenAI gpt-image-2

Финальная генерация — **один вызов** `client.images.edit(...)` с массивом из двух картинок (сцена + товар) и текстовым промптом.

Файл: `ai/generation.py`. Промпт: `GENERATION` в `ai/prompts.py`.

## Контракт

```python
async def generate_room_with_product(
    scene_url: str,
    product_url: str,
    to_remove_en: str,
    to_remove_ru: str,
    to_add_en: str,
    to_add_ru: str,
    ceiling_cm: int,
    room_description: str,
    product_dims_cm: tuple[float, float, float],
) -> dict
```

Возвращает:
```python
{
    "success": bool,
    "image_bytes": bytes | None,  # PNG итоговой картинки
    "error": str | None,
    "error_type": "api" | "network" | "unknown" | None,
    "cost_estimate_usd": float,
    "duration_sec": int,
    "model": "gpt-image-2",
    "quality": "medium",
    "size": "1536x1024" | "1024x1024" | "1024x1536",
}
```

## Стратегия

1. **Скачиваем обе картинки** с 0x0.st (или catbox) как bytes — SDK 2.36 принимает только файлы, не URL.
2. **Выбираем размер выхода** по ориентации фото комнаты:
   - Горизонтальное (ratio ≥ 1.25): `1536x1024`
   - Вертикальное (ratio ≤ 0.8): `1024x1536`
   - Иначе: `1024x1024`
3. **Вызываем `client.images.edit`** с моделью `gpt-image-2`, `input_fidelity="high"`, `quality="medium"`.
4. **Fallback на `gpt-image-1.5`** если основная модель недоступна (ошибка типа "model not found").
5. **Извлекаем результат**: сначала `b64_json` (если есть), иначе скачиваем по `url`.

## Параметры окружения

| ENV | По умолчанию | Зачем |
|---|---|---|
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` | Модель генерации. Можно переключить на `gpt-image-1.5`/`gpt-image-1-mini`. |
| `OPENAI_IMAGE_QUALITY` | `medium` | `low` $0.006 / `medium` $0.024 / `high` $0.12 за картинку. |
| `OPENAI_IMAGE_INPUT_FIDELITY` | `high` | `high` сохраняет визуал товара, `low` ускоряет/удешевляет. |
| `OPENAI_BASE_URL` | (опц.) | Прокси gptproxy на сервере: `http://host.docker.internal:8089/gpt`. |

## Промпт

Английский, акцент на двух вещах:
- **Сохранение визуала товара** — exact color/pattern/shape/materials
- **Сохранение целостности сцены** — стены/пол/потолок/окна/освещение не трогать

Полный текст в `ai/prompts.py` → `GENERATION`.

## Стоимость и время

| Параметр | Значение |
|---|---|
| Цена за картинку (medium) | ~$0.024 |
| Цена полного flow (QC + slot estimate + generation) | ~$0.033 |
| Время генерации | 20-40 сек |
| Время полного flow от пользователя | ~30-60 сек активного ожидания |

## Edge cases

| Случай | Поведение |
|---|---|
| OpenAI вернул `b64_json` | Декодируем base64 → bytes |
| OpenAI вернул `url` | Скачиваем картинку → bytes |
| Модель `gpt-image-2` недоступна для аккаунта (требуется верификация) | Fallback на `gpt-image-1.5` |
| Сеть упала при скачивании reference | `error_type="network"`, пользователю сообщение, не повторяем (пусть /start) |
| OpenAI rate limit (429) | `error_type="api"`, сообщение пользователю, не повторяем автоматически |
| Картинка > поддерживаемого размера | `preprocess_image()` (ai/preprocessing.py) уже ужал до 1280px при загрузке |

## Что НЕ делаем

- ❌ Best-of-N (`n>1`) — для теста хватает одного варианта, удваивает цену
- ❌ Кэширование результатов — каждый пользователь уникален
- ❌ Промежуточные validation метрики (CLIP-I, SSIM, Grounding DINO) — это был план в Шаге 4 с Replicate, при gpt-image-2 решено отказаться

## Связанные файлы

- `ai/prompts.py::GENERATION` — текст промпта
- `handlers.py::_finish` — вызов и отправка результата в Telegram
- `db.py::log_generation` — сохранение факта генерации (успех/фейл, цена, длительность)
- `.memory_bank/_claude/DECISIONS.md` — обоснование отказа от Replicate
