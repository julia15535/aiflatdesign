# Docker (изолированный деплой)

Цель: бот запускается в Docker контейнере под user'ом 1000 на сервере 193.160.208.41 рядом с другими проектами, **никак** их не трогая.

## Целевая структура на сервере

```
/opt/aiflatdesigner/
├── docker-compose.yml
├── Dockerfile
├── .env                    # секреты, не в git
├── .dockerignore
├── pyproject.toml
├── bot.py
├── pipeline.py
├── db.py
├── ai/, bot/, utils/
├── assets/tutorial/
└── data/                   # volume mount
    └── prototype.db
```

## Dockerfile (целевой)

Multistage build для маленького финального образа.

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir .

FROM python:3.11-slim
WORKDIR /app
# Только runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# Скопировать installed packages из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Код
COPY bot.py pipeline.py db.py metrics.py ./
COPY ai/ ./ai/
COPY bot/ ./bot/
COPY utils/ ./utils/
COPY assets/ ./assets/
# Non-root user
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    chown -R botuser:botuser /app
USER botuser
CMD ["python", "bot.py"]
```

⚠️ `opencv-python-headless` (не `opencv-python`) в pyproject.toml — экономит ~150 MB и не тянет GUI deps. Системные libGL и libglib2.0 — нужны opencv'ю.

## docker-compose.yml

```yaml
services:
  bot:
    build: .
    container_name: aiflatdesigner-bot
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    networks:
      - aiflatdesigner-net
    extra_hosts:
      # Доступ к хостовому gptproxy (на :8089) — без этого OpenAI запросы не пройдут
      - "host.docker.internal:host-gateway"
    # Никаких ports — long polling.

networks:
  aiflatdesigner-net:
    name: aiflatdesigner-net
    driver: bridge
```

Ключевые моменты:
- **container_name** — `aiflatdesigner-bot` (уникальный, не пересекается с существующими).
- **networks** — отдельная `aiflatdesigner-net`, не дефолтный bridge, чтобы не пересечься с другими сервисами на сервере.
- **volume** — `./data` хостовая папка ↔ `/app/data` в контейнере (для prototype.db).
- **restart: unless-stopped** — переживает рестарт сервера, но не мешает остановить руками.
- **extra_hosts** — критично: даёт `host.docker.internal` в DNS контейнера → доступ к хостовому gptproxy (`http://host.docker.internal:8089/gpt`).
- **Никаких ports** — Telegram bot long polling работает по исходящим к api.telegram.org:443.

## .dockerignore

```
.git
.gitignore
.memory_bank/
.claude/
docs/
memory_bank_reference/
data/
*.db
*.db-journal
__pycache__/
*.pyc
.venv/
.env
.env.local
README.md
```

⚠️ `.env` исключаем из образа — он пробрасывается через `env_file:` в compose, в образе его быть не должно.

## .env (на сервере)

```bash
# Файл: /opt/aiflatdesigner/.env  — права 600, owner root
TG_BOT_TOKEN=<from @BotFather, см. _claude/SECRETS.md>
REPLICATE_API_TOKEN=r8_...
OPENAI_API_KEY=sk-proj-...
# Прокси через хостовой gptproxy (тот же что у med.2opinion.online)
OPENAI_BASE_URL=http://host.docker.internal:8089/gpt
ADMIN_TG_ID=...
TEST_MODE=false
COST_LIMIT_USD=300
SIZE_TOLERANCE_PCT=15
OPENAI_VISION_MODEL=gpt-5.4-mini
OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-mini
QUALITY_CHECK_ENABLED=true
```

После создания — `chmod 600 .env`.

## Команды деплоя

```bash
# первый раз
ssh root@193.160.208.41
mkdir -p /opt/aiflatdesigner
cd /opt/aiflatdesigner
# Перенос файлов: git clone или scp -r (см. infra/github.md или _claude/DEPLOY.md)
nano .env  # создать с реальными токенами
chmod 600 .env
docker compose build
docker compose up -d
docker logs aiflatdesigner-bot --tail 100 -f

# обновление
cd /opt/aiflatdesigner
git pull
docker compose build
docker compose up -d
```

## Health check (опционально)

Можем добавить healthcheck скрипт — проверяет что Telegram polling активен:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import os, sys, sqlite3; sys.exit(0 if os.path.exists('/app/data/prototype.db') else 1)"]
  interval: 5m
  timeout: 10s
  retries: 3
```

Простая проверка: если БД создалась — бот стартовал хотя бы раз.

## Размер образа — цель

| Часть | Размер |
|---|---|
| python:3.11-slim | ~120 MB |
| + libGL, libglib | +20 MB |
| + Python deps (aiogram, openai, replicate, Pillow, numpy, opencv-headless, scikit-image, httpx) | +900 MB |
| + Наш код | +5 MB |
| **Итого** | **~1.0-1.1 GB** |

С диском 6.1 GB свободно — должны уложиться, оставляя ~5 GB запаса.

## Сборка для других платформ

На Windows-машине разработчика собирать не надо. Деплой:

1. `git push` в GitHub
2. На сервере `git pull`
3. На сервере `docker compose build`

Не используем `docker-compose build` на Windows и `docker push` в registry — лишняя сложность для MVP.

## Анти-паттерны

- ❌ `--network host` — наш бот окажется в одной сети с другими проектами.
- ❌ `volumes: /opt:/opt` — никаких bind mount'ов наружу нашей папки.
- ❌ Запуск под root в контейнере — `USER botuser` обязательно.
- ❌ `:latest` тег без явной версии — для MVP не критично, но желательно тегировать `v0.1`.
- ❌ Build на сервере с диском 88% — сначала проверить `docker system df` и почистить если надо.
