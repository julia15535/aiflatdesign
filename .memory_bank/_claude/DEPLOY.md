# Deploy на 193.160.208.41

Полная инструкция для деплоя проекта на прод-сервер.

## Pre-flight (один раз)

1. Убедиться что репо есть на GitHub: https://github.com/julia15535/aiflatdesign
2. Убедиться что SSH ключ id_ed25519 добавлен в GitHub keys (для git pull на сервере)
3. Убедиться что в `.env` все токены — TG/Replicate/OpenAI
4. На локальной машине: `git push -u origin main`

## Первый деплой

```bash
# 1. Подключиться к серверу
ssh root@193.160.208.41

# 2. Проверить место на диске (должно быть >2 GB свободно)
df -h /
# Если меньше 2 GB — почистить:
docker system prune -af   # ⚠️ удаляет неиспользуемые images/контейнеры

# 3. Создать папку
mkdir -p /opt/aiflatdesigner
cd /opt/aiflatdesigner

# 4. Клонировать репо
git clone git@github.com:julia15535/aiflatdesign.git .
# Если ключ NA добавлен — HTTPS вариант:
# git clone https://github.com/julia15535/aiflatdesign.git .

# 5. Создать .env (НЕ из git!)
nano .env
# Вставить:
# TG_BOT_TOKEN=...
# REPLICATE_API_TOKEN=r8_...
# OPENAI_API_KEY=sk-...
# ADMIN_TG_ID=...
# (+ остальные см. .env.example)
chmod 600 .env

# 6. Создать папку для данных
mkdir -p data
chown -R 1000:1000 data   # uid 1000 = botuser в контейнере

# 7. Собрать и запустить
docker compose build --no-cache
docker compose up -d

# 8. Проверить логи
docker logs aiflatdesigner-bot --tail 100 -f
# Ctrl+C для выхода из follow
```

## Обновление кода (последующие деплои)

```bash
ssh root@193.160.208.41
cd /opt/aiflatdesigner

# Простой случай: только код, без новых deps
git pull
docker compose restart

# С новыми зависимостями в pyproject.toml
git pull
docker compose build
docker compose up -d
```

## Откат

```bash
ssh root@193.160.208.41
cd /opt/aiflatdesigner

# Найти предыдущий коммит
git log --oneline -10

# Откатить
git reset --hard <commit-sha>
docker compose build
docker compose up -d
```

⚠️ `git reset --hard` уничтожает любые локальные изменения на сервере. Если есть hot-fix в `.env` или `data/` — сохранить заранее.

## Бэкап БД

```bash
ssh root@193.160.208.41
cd /opt/aiflatdesigner/data
cp prototype.db prototype.db.bak-$(date +%Y%m%d)

# Cron для ежедневного бэкапа (если ставим):
# 0 4 * * * cd /opt/aiflatdesigner/data && cp prototype.db prototype.db.bak-$(date +\%Y\%m\%d) && find . -name 'prototype.db.bak-*' -mtime +7 -delete
```

## Проверка здоровья

```bash
# Бот жив?
docker ps | grep aiflatdesigner-bot

# Свежий лог
docker logs aiflatdesigner-bot --tail 20

# Telegram polling работает?
docker logs aiflatdesigner-bot 2>&1 | grep "getUpdates" | tail -5

# Размер БД
ls -lah /opt/aiflatdesigner/data/prototype.db

# Сколько генераций в БД
docker exec aiflatdesigner-bot python -c "import sqlite3; print(sqlite3.connect('/app/data/prototype.db').execute('SELECT COUNT(*) FROM generations').fetchone())"
```

## Остановить

```bash
ssh root@193.160.208.41
cd /opt/aiflatdesigner
docker compose down
# Контейнер остановлен, volume `data/` сохранён
```

## Полное удаление

```bash
# ⚠️ ВНИМАНИЕ: удалит ВСЁ включая БД!
ssh root@193.160.208.41
cd /opt/aiflatdesigner
docker compose down -v   # -v удалит docker volumes (у нас их нет, но на всякий)
cd ..
rm -rf /opt/aiflatdesigner
docker image rm aiflatdesigner-bot
docker network rm aiflatdesigner-net
```

## Troubleshooting

| Симптом | Что проверить |
|---|---|
| `docker compose build` падает с no space left | `df -h /`, потом `docker system prune -af` |
| Бот стартует но не отвечает в Telegram | TG_BOT_TOKEN валидный? `docker logs ...` |
| `getUpdates` 401 Unauthorized | Token revoked в @BotFather — взять новый |
| Pipeline валится на OpenAI 429 | Rate limit. Подождать минуту или повысить tier |
| Pipeline валится на Replicate 503 | Cold start, попробовать ещё раз. Или сменить модель |
| no space left во время generation | 0x0.st не сохраняет на сервер — мы тратим только память. Проверить `docker stats` |
| FSM "зависает" | Бот рестартовал. Пользователь /start заново |

## Точки безопасности

- ⚠️ Папка `/opt/aiflatdesigner/` имеет права `700` (только root читает).
- ⚠️ `.env` файл — `chmod 600`, только root.
- ⚠️ `data/` принадлежит uid 1000 (botuser в контейнере).
- ✅ Никаких портов в `0.0.0.0` — все привязки только к 127.0.0.1 если будут (но сейчас не нужны).
