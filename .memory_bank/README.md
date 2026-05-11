# AI Flat Designer — Memory Bank

⚠️ **Единая точка правды для проекта.** Всё сюда пишу, всё отсюда читаю. Системная Claude memory (`~/.claude/projects/.../memory/`) хранит только короткие pointer'ы на этот banks.

## Что за проект

**AI Flat Designer** — Telegram-бот, который вписывает мебель/декор из фото товара (каталожное фото) в фото комнаты пользователя. Сохраняет visual identity товара (цвет, паттерн, форма) и контролирует размер (±15%).

**MVP за 6-8 дней, бюджет $200-280.** Источник правды по продукту: [`docs/MVP_PROTOTYPE_v4.md`](../docs/MVP_PROTOTYPE_v4.md).

## Структура

```
.memory_bank/
├── README.md              ← вы здесь
├── CLAUDE.md              — manifest проекта (стек, домен, правила)
├── product_brief.md       — целевая аудитория, use case, бизнес-цели
├── product_roadmap.md     — план по дням (1-8)
│
├── guides/                — общие правила (как писать, как работать)
│   ├── plan_template.md   — формат файла плана
│   ├── documentation_style.md — что и как писать в memory bank
│   └── lang.md            — русский для документации, английский для кода
│
├── domain/                — модели не зависящие от платформы
│   ├── pipeline.md        — Stage 0-5 pipeline overview
│   ├── states.md          — FSM bot states
│   └── data_model.md      — SQLite schema (users, sessions, generations)
│
├── ai/                    — AI integrations
│   ├── openai_vision.md   — GPT-5.4 Mini: quality_check, scene_analysis, product_desc
│   ├── replicate.md       — FLUX Fill Pro, GroundedSAM, Clarity Upscaler, GroundingDINO, CLIP
│   ├── quality_check.md   — Stage 0
│   ├── scene_analysis.md  — Stage 1
│   ├── size_check.md      — Stage 2 (геометрия слота)
│   ├── generation.md      — Stage 3 (best-of-N inpainting)
│   ├── validation.md      — Stage 4 (CLIP-I, SSIM, presence, WOW score)
│   ├── upscaling.md       — Stage 5
│   ├── prompts.md         — все промпты в одном месте
│   └── fail_patterns.md   — типичные провалы и как обрабатываем
│
├── bot/                   — Telegram bot слой
│   ├── flow.md            — полный flow пользователя
│   ├── onboarding.md      — туториал + 4 visual asset
│   ├── commands.md        — /start /help /cancel /myhistory
│   └── handlers.md        — FSM, callback handlers
│
├── infra/                 — деплой и операционка
│   ├── server.md          — 193.160.208.41, существующие проекты, свободные порты, диск
│   ├── docker.md          — изоляция нашего проекта, docker-compose
│   ├── github.md          — репо julia15535/aiflatdesign
│   └── secrets_template.md — какие токены нужны (без значений)
│
├── plans/                 — активные планы (формат — см. guides/plan_template.md)
├── completed_plans/       — архив выполненных планов
│
├── _claude/               — Claude internal (НЕ для git: SECRETS.md в .gitignore)
│   ├── INDEX.md           — стартовый указатель: что читать в какой ситуации
│   ├── PROJECT-STATE.md   — текущее состояние проекта (фаза, статусы, бюджет)
│   ├── DECISIONS.md       — архитектурные решения
│   ├── DEPLOY.md          — конкретные команды деплоя на сервер
│   ├── workflow.md        — как Claude работает в этом проекте
│   └── SECRETS.md         — все токены (gitignored!)
│
└── business/              — бизнес-заметки
    └── budget.md          — бюджет $200-280, разбивка
```

## Правила

**Перед фичей** — заглянуть в `domain/` и `ai/` (это контракты pipeline).

**После решения** — зафиксировать в правильном файле и закоммитить.

**Секреты** — только в `_claude/SECRETS.md` (gitignored). В коде только через `.env`.

**Дата** — конвертирую относительные даты в абсолютные при сохранении (Today's date: 2026-05-11).

**Язык документации** — русский. Названия переменных/функций/команд — английский.

## Источники

- Полная спецификация MVP: [`docs/MVP_PROTOTYPE_v4.md`](../docs/MVP_PROTOTYPE_v4.md)
- Целевой GitHub репо: https://github.com/julia15535/aiflatdesign
- Server: 193.160.208.41 (root через `~/.ssh/id_ed25519`)
