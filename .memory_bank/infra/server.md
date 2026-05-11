# Server: 193.160.208.41

Корневой root-доступ через SSH ключ `~/.ssh/id_ed25519`. Hostname: `4905763-ty25404` (Ubuntu 22.04 / kernel 5.15).

## Доступ

```bash
ssh -i ~/.ssh/id_ed25519 root@193.160.208.41
```

SSH config уже прописан в `~/.ssh/config`:

```
Host 193.160.208.41
  HostName 193.160.208.41
  User root
```

Ключ `id_rsa_2` НЕ работает на этом сервере — только `id_ed25519`.

## Что уже запущено

⚠️ **Не ломать!** Существующие проекты:

| Контейнер | Status | Порты (на хосте) | Папка |
|---|---|---|---|
| `wfm-admin` | up ~1ч | 127.0.0.1:3004→3000 | `/opt/wfm-admin` |
| `med-frontend` | up 43ч | 127.0.0.1:3003→3000 | (не /opt) |
| `med-backend` | up 6 нед | 127.0.0.1:8001→8000 | |
| `med-db` (postgres) | up 6 нед | 127.0.0.1:15432→5432 | |
| `sup-frontend` | up 6 нед | 127.0.0.1:3002→3000 | |
| `remnanode` | up 5 нед | (нет проброса) | `/opt/remnanode` |
| `siberian-frontend` | up 3 мес | 0.0.0.0:3001 | |
| `strapi` | up 3 мес | 0.0.0.0:1337 | |
| `strapiDB` (mysql) | up 3 мес | 0.0.0.0:3306 | |
| `gptproxy` (нативный) | bind :8089 | | `/opt/gptproxy` |
| `zabbix_agentd` | running | :10050 | |

## Свободные порты на хосте

Все ниже **СВОБОДНЫ** на 2026-05-11. Для нашего бота **порты не нужны** (long polling — outbound only), но если понадобится локальный health-endpoint:

- 3005-3010 (рядом с frontends)
- 8002-8088 (рядом с med-backend)
- 8090-9000 (рядом с gptproxy)

Привязываемся ВСЕГДА к `127.0.0.1:PORT`, не к `0.0.0.0`, чтобы не светить наружу.

## Диск

```
/dev/sda1   50G    44G used    6.1G free   88%
```

⚠️ **Критично:** только 6.1 GB свободно. Для нашего проекта:
- Python 3.11 slim image ≈ 120 MB
- + venv с deps (aiogram, openai, replicate, Pillow, numpy, opencv, scikit-image) ≈ 600 MB
- + opencv-python (тяжёлый): ~300 MB сам по себе
- Логи и данные: ~100 MB первое время

Целевой image size: **≤1.5 GB**. Если соберём 4-5 GB — упрёмся в no space left.

### Оптимизации

- Use `python:3.11-slim` (а не `python:3.11`)
- Multistage build чтобы не тащить build-tools в финальный образ
- Установить `opencv-python-headless` вместо `opencv-python` — без GUI зависимостей, на ~150 MB меньше
- `.dockerignore` исключает `data/`, `tests/`, `*.db`

### Чистка перед деплоем

```bash
docker system prune -af --volumes  # ⚠️ удалит unused images/volumes
# При запуске на этом серваке БЕЗ --volumes (там могут быть данные других проектов)
```

## Backup структура

В `/root/`:
- `backup-before-med-2026-03-27-233922/` — точка возврата перед запуском med
- `backup-before-sup-2026-03-26-225107/` — перед sup
- Архивы: `v0-health-card.tar.gz`, `v0-sup-main.tar.gz`

Полезно: перед нашим деплоем сделать `backup-before-aiflatdesigner-YYYY-MM-DD-HHMMSS/` (на всякий).

## Наш проект — целевая папка

```
/opt/aiflatdesigner/
├── docker-compose.yml
├── Dockerfile
├── .env                  # секреты, gitignored
├── bot.py
├── pipeline.py
├── ai/
├── ...
└── data/
    └── prototype.db      # mounted volume, чтобы не терять при redeploy
```

См. `infra/docker.md` для docker-compose.

## Nginx

Сервер использует nginx (80/443). **Нам он не нужен** — long polling Telegram'а работает по исходящим. Если в будущем понадобится webhook — добавим конфиг в `/etc/nginx/sites-available/`, но это уже не MVP.

## Мониторинг

- Zabbix agent уже стоит (:10050) — собирает метрики CPU/RAM/диск
- Логи бота: `docker logs aiflatdesigner-bot --tail 200`
- Файловые логи: в Docker volume `/opt/aiflatdesigner/data/logs/`

## Точки безопасности

- ❌ Не открывать порты Telegram-бота наружу (long polling нам не нужен).
- ❌ Не использовать `0.0.0.0:PORT` биндинги без необходимости.
- ❌ Не делать `chmod 777` на /opt/aiflatdesigner.
- ✅ Token Telegram бот'а — только в `.env`, не в git, не в memory_bank (кроме `_claude/SECRETS.md`).
- ✅ Запуск в Docker под non-root user'ом (uid 1000).
