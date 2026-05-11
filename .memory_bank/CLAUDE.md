# CLAUDE.md — AI Flat Designer

Manifest проекта для Claude Code. При работе сначала читай этот файл, потом ныряй в `domain/`, `ai/`, `bot/` по необходимости.

## Обзор проекта

**AI Flat Designer** — Telegram-бот, вписывающий мебель из каталожных фото товаров в фото комнат пользователя. Использует OpenAI vision для анализа сцены и Replicate (FLUX Fill Pro) для генерации.

**Цель MVP**: за 6-8 дней проверить даёт ли подход WOW ≥3.5/5 и success rate ≥70% на средних сценах при условии что пользователь следует инструкциям и фото нормального качества.

## Бизнес-контекст

**Платящие сегменты**: ритейлеры мебели (Hoff, Divan.ru), производители (Аскона, Mr.Doors), застройщики, дизайнеры.

**Use case**: пользователь грузит фото комнаты + фото товара → бот вписывает товар в комнату с сохранением visual identity (цвет, паттерн, форма) и контролем размера (±15%).

Подробнее: `product_brief.md`.

## Стек

- **Язык**: Python 3.11+
- **Bot framework**: aiogram 3.x (long polling, без webhook)
- **AI**: openai≥1.50.0 (GPT-5.4 Mini vision), replicate (FLUX Fill Pro, GroundedSAM, Clarity Upscaler, Grounding DINO, CLIP)
- **Обработка изображений**: Pillow, numpy, opencv-python, scikit-image (SSIM)
- **Хранилище**: SQLite (логи), 0x0.st (temp public URLs для AI API)
- **HTTP**: httpx
- **Конфиг**: python-dotenv
- **Пакетный менеджер**: uv (рекомендуется)

## Архитектура pipeline

```
User → Bot (FSM) → Pipeline:
  Stage 0: Quality Check    (GPT-5.4 Mini vision, low detail)
  Stage 1: Scene Analysis   (GPT-5.4 Mini vision, high detail) + GroundedSAM (slot mask)
  Stage 2: Pre-flight Size  (алгоритм: bbox → real cm с учётом room dimensions)
  Stage 3: Generation       (FLUX Fill Pro × 3 seeds, best-of-N)
  Stage 4: Validation       (CLIP-I, SSIM, Grounding DINO presence, WOW score)
  Stage 5: Optional Polish  (Clarity Upscaler 2×)
```

Полное описание stage'ей в `ai/{quality_check,scene_analysis,size_check,generation,validation,upscaling}.md`.

## FSM бота (упрощённо)

```
onboarding_step_1..4 (только при первом /start)
  ↓
waiting_scene → quality_check → ok/warn/reject
  ↓
waiting_room_dims (опционально)
  ↓
waiting_target_class (sofa / armchair / bed / lamp / ...)
  ↓
waiting_product_photo → quality_check → ok/warn/reject
  ↓
waiting_product_dims (опционально)
  ↓
[Pipeline запуск] → confirming_warning при size mismatch
  ↓
Результат с rating buttons (👍 / 😐 / 👎)
```

Подробнее: `bot/flow.md`, `bot/handlers.md`.

## Структура проекта (целевая)

```
aiflatdesigner/
├── bot.py
├── states.py            # FSM
├── handlers.py
├── pipeline.py          # главный orchestrator
├── db.py
├── metrics.py
├── ai/
│   ├── preprocessing.py
│   ├── quality_check.py
│   ├── scene_analysis.py
│   ├── size_check.py
│   ├── generation.py
│   ├── validation.py
│   ├── upscaling.py
│   └── prompts.py
├── utils/
│   ├── storage.py       # 0x0.st upload
│   └── geometry.py
├── assets/tutorial/     # 4 картинки для онбординга
├── data/
│   ├── test_inspirations/{easy,medium,hard}/
│   ├── test_catalog/
│   └── results/
├── scripts/
│   ├── benchmark.py
│   └── eval_results.py
├── pyproject.toml
├── .env.example
└── .env                 # gitignored
```

## .env (контракт)

```bash
TG_BOT_TOKEN=...
REPLICATE_API_TOKEN=r8_...
OPENAI_API_KEY=sk-proj-...
# Прокси через локальный gptproxy на сервере (тот же что med.2opinion.online)
OPENAI_BASE_URL=http://host.docker.internal:8089/gpt
ADMIN_TG_ID=...
TEST_MODE=true
COST_LIMIT_USD=300
SIZE_TOLERANCE_PCT=15
OPENAI_VISION_MODEL=gpt-5.4-mini
OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-mini
QUALITY_CHECK_ENABLED=true
SKIP_ONBOARDING_FOR_DEV=false
```

## OpenAI через прокси (gptproxy)

OpenAI вызовы идут через **локальный gptproxy** на сервере (`/opt/gptproxy/gptproxy`, systemd unit `gptproxy.service`, порт `*:8089`). Тот же прокси использует проект `med.2opinion.online` на этом сервере — мы переиспользуем подход и ключ.

Логика прокси (Go): `/gpt/*` → `https://api.openai.com/v1/*` (стирает префикс `/gpt`).

В коде:
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),   # http://host.docker.internal:8089/gpt
)
```

В docker-compose обязательно:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Иначе из контейнера не достучаться до хостового gptproxy.

## Принципы

1. **Memory Bank — источник правды.** Перед фичей читаем `.memory_bank/`.
2. **Минимальная сложность.** MVP не нужны абстракции на вырост, делаем по спеке.
3. **Длинная задача → план.** Если фича >3 шагов — создаём `plans/<name>.md`, после выполнения переносим в `completed_plans/`.
4. **Логируем всё.** Все сессии и генерации идут в SQLite — потом анализируем failure cases.
5. **Quality check API падает → не блокируем.** Fallback: skip QC, идём дальше с warning в логах.
6. **0x0.st temporary URLs.** Replicate и OpenAI оба берут картинки по URL — храним в 0x0.st кратко (1 час) и удаляем.
7. **Stateless bot.** FSM в памяти (MemoryStorage). Если упал — пользователь начинает с `/start`. БД только для логов и онбординга.
8. **Лимиты:** 5 регенераций / пользователь / день. Защита от спама + бюджет.
9. **Изоляция на сервере.** Деплой в `/opt/aiflatdesigner`, отдельный docker-compose, никаких портов наружу (long polling). См. `infra/docker.md`.

## Метрики и Go/No-go

| Метрика | Easy | Medium | Hard |
|---|---|---|---|
| WOW score | ≥3.8 | ≥3.3 | ≥2.5 |
| Success rate | ≥80% | ≥60% | ≥40% |
| Catalog fidelity | ≥0.78 | ≥0.72 | ≥0.65 |
| Size deviation | ≤15% | ≤25% | ≤40% |
| User 👍 | ≥75% | ≥55% | ≥35% |
| Cost / gen | <$0.20 | <$0.30 | <$0.50 |
| Duration | <75s | <90s | <120s |

Подробное Go/No-go дерево решений — в `docs/MVP_PROTOTYPE_v4.md` ("Метрики и Go/No-go").

## Workflow с планами

При начале сессии:
1. Прочитать `MEMORY.md` в auto-memory (системная Claude memory).
2. Проверить `.memory_bank/plans/` — есть незавершённые?
3. Если да — предложить продолжить.

При фиче >3 шагов:
1. Создать `plans/<name>.md` со статусом, целью, чек-листом задач.
2. По мере выполнения — ставить `[x]` и обновлять "Последнее обновление".
3. По окончании — статус "Выполнено", переместить в `completed_plans/`.

## Язык документации

Документация (memory bank, README, комментарии в коде) — на **русском**.
Имена переменных/функций, команды, технические термины — на **английском**.

## Что делать НЕ надо

- ❌ Открывать порты наружу — Telegram bot работает long polling.
- ❌ Хранить секреты в memory bank (только в `_claude/SECRETS.md`, gitignored).
- ❌ Ставить тяжёлые vision-модели локально — всё через API.
- ❌ Кэшировать картинки пользователей — gdpr, диск.
- ❌ Использовать webhook — long polling проще для MVP.
- ❌ Деплой без `--name` контейнера и без отдельной docker network — можно случайно зацепить чужие контейнеры на сервере.
