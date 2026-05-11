# Secrets template

Список всех токенов и секретов, нужных проекту. **Значения** — в `_claude/SECRETS.md` (gitignored).

## Текущий статус

| Secret | Что | Получить | Статус |
|---|---|---|---|
| `TG_BOT_TOKEN` | Telegram bot token | @BotFather | ✅ Есть |
| `REPLICATE_API_TOKEN` | Replicate API (FLUX, GroundedSAM, ...) | https://replicate.com/account | ✅ Есть |
| `OPENAI_API_KEY` | OpenAI API (GPT-5.4 Mini vision) | переиспользуем от med.2opinion.online | ✅ Есть |
| `OPENAI_BASE_URL` | Прокси через хостовой gptproxy | `http://host.docker.internal:8089/gpt` | ✅ Зафиксировано |
| `ADMIN_TG_ID` | TG ID админа для error notifications | @userinfobot в Telegram | ⏳ TODO (есть `@my_coruja`, нужен numeric ID) |

## .env.example (в репо)

```bash
# Telegram
TG_BOT_TOKEN=                    # token бот'а от @BotFather

# AI APIs
REPLICATE_API_TOKEN=r8_...
OPENAI_API_KEY=sk-...

# Settings
ADMIN_TG_ID=                     # для error notifications
TEST_MODE=false
COST_LIMIT_USD=300
SIZE_TOLERANCE_PCT=15

# Model overrides
OPENAI_VISION_MODEL=gpt-5.4-mini
OPENAI_QUALITY_CHECK_MODEL=gpt-5.4-mini
QUALITY_CHECK_ENABLED=true
SKIP_ONBOARDING_FOR_DEV=false
```

## SSH ключи

| Ключ | Где | Что |
|---|---|---|
| `~/.ssh/id_ed25519` | Win machine разработчика | SSH в сервер 193.160.208.41 + GitHub |
| `~/.ssh/id_rsa_2` | Win machine | (не для этого сервера) |

## Что хранить локально

⚠️ **Не пушим в git**:
- `.env` (рабочий)
- `_claude/SECRETS.md` (полный список значений)
- `*.key`, `*.pem`

## Ротация

При компрометации:
1. Telegram token: @BotFather → /revoke
2. OpenAI key: dashboard → revoke + new key
3. Replicate: dashboard → reset

После ротации:
- Обновить `_claude/SECRETS.md`
- Обновить `.env` на сервере (`ssh root@... vim /opt/aiflatdesigner/.env`)
- Рестарт: `docker compose restart`
