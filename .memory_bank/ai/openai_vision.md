# OpenAI Vision (GPT-5.4 Mini)

Все vision-задачи в MVP идут через **GPT-5.4 Mini** ($0.75/$4.50 за 1M input/output tokens). В 3× дешевле GPT-4o, в 1.4× дешевле Claude Sonnet vision.

## SDK

```
pip install -U openai>=1.50.0
```

≥1.50 — обязательно, в старых версиях нет нормальной поддержки GPT-5.4 семейства.

## Подключение через локальный gptproxy

На сервере 193.160.208.41 уже работает `gptproxy` (Go reverse proxy) на `*:8089`. Используем его, переиспользуя ключ от соседнего проекта `med.2opinion.online`.

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),   # http://host.docker.internal:8089/gpt
)
```

`gptproxy` стирает префикс `/gpt` и форвардит запрос на `https://api.openai.com/v1/*`. Аутентификация — стандартный `Authorization: Bearer <api_key>` через SDK.

⚠️ Если `OPENAI_BASE_URL` пустой — SDK по умолчанию пойдёт напрямую на `api.openai.com`. Это OK для локального dev (можно так), но в prod (в docker контейнере на сервере) — всегда через прокси.

## Модели

| Что | env var | По умолчанию | Можно переключить на |
|---|---|---|---|
| Все vision-задачи | `OPENAI_VISION_MODEL` | `gpt-5.4-mini` | (не трогаем для MVP) |
| Quality check (Stage 0) | `OPENAI_QUALITY_CHECK_MODEL` | `gpt-5.4-mini` | `gpt-5.4-nano` (экономия ~$0.003/flow) |

**Scene analysis и product description оставляем на Mini** — Nano не «text-first worker» по доке.

## Общий паттерн

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()  # ключ через env OPENAI_API_KEY

response = await client.chat.completions.create(
    model=model_name,
    response_format={"type": "json_object"},  # для JSON-промптов
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT_TEXT},
            {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
        ]
    }],
    max_tokens=600,
)
result = json.loads(response.choices[0].message.content)
```

## detail: "low" vs "high"

| Detail | Что | Когда брать |
|---|---|---|
| `low` | Картинка ужимается до 512×512, ~85 input tokens | Quality check, product description (детали не критичны) |
| `high` | Полная обработка, до 765 input tokens на «tile» | Scene analysis (нужно считать ориентиры — двери, окна, плинтус) |

## response_format

**Всегда** используем `{"type": "json_object"}` для структурированных промптов. Тогда:
- Ответ гарантированно валидный JSON
- Не нужен parser с try/except — сразу `json.loads()`

## Async

**Только** `AsyncOpenAI()`, не `OpenAI()`. В aiogram-боте критично чтобы не блокировать event loop при vision-вызове (1-3 сек на запрос).

## Rate limits и retries

- Free tier: 3 RPM (слишком мало для бенчмарка)
- Paid tier: 500+ RPM (хватает с запасом)
- SDK поддерживает `max_retries=N` — для прототипа `max_retries=3` (default).

## Стоимость в одном flow

| Шаг | Detail | Цена |
|---|---|---|
| Scene quality check | low | $0.002 |
| Product quality check | low | $0.002 |
| Scene analysis | high | $0.003 |
| Product description | low | $0.001 |
| **Итого OpenAI часть** | | **~$0.008** |

## Cost monitoring

Каждый ответ возвращает `response.usage.total_tokens`. Если хотим тонко мониторить — складываем в БД. На MVP — достаточно `cost_usd` per generation.

## Передача image_url

OpenAI принимает картинки по публичному URL. Используем 0x0.st (см. `utils/storage.py`). URL живёт ~1 час, для async pipeline хватает.

⚠️ **Не передаём base64**: получим 30-100 KB на запрос вместо нескольких сотен байт URL'а. Существенно медленнее и дороже по tokens.

## Промпты

Все промпты собраны в `ai/prompts.md`. Не дублируем в коде — импортируем оттуда.

## Failure modes

| Что | Поведение | Fallback |
|---|---|---|
| Timeout (>10 сек) | SDK кидает APIConnectionError | Логируем, делаем retry до 3 раз |
| Invalid JSON (теоретически невозможно с response_format) | Проверка `json.loads` упадёт | Лог + skip stage (warn user) |
| Rate limit | 429 RateLimitError | SDK сам делает exponential backoff |
| Plain refusal (модель отказалась) | Содержимое начинается с "I'm sorry" | На vision-задачах не должно случаться; если случилось — fallback на default JSON `{"recommendation":"warn_user", ...}` |
