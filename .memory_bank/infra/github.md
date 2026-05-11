# GitHub репо

**URL**: https://github.com/julia15535/aiflatdesign
**Owner**: julia15535
**Visibility**: (уточнить — public или private)

## Доступ для пуша

Через SSH ключ `~/.ssh/id_ed25519` (тот же что для сервера). Проверка `ssh -T git@github.com` — должен ответить "Hi julia15535! ...".

Если ключ ещё НЕ добавлен на GitHub — пользователю надо:
1. Скопировать `~/.ssh/id_ed25519.pub`
2. https://github.com/settings/keys → New SSH key

Альтернатива: PAT через HTTPS — но SSH стабильнее для CI.

## Git remote

```bash
git remote add origin git@github.com:julia15535/aiflatdesign.git
```

## .gitignore (корневой)

```
# venv / зависимости
.venv/
__pycache__/
*.pyc
.pytest_cache/

# secrets
.env
.env.local

# данные
data/*.db
data/*.db-journal
data/results/
data/test_inspirations/
data/test_catalog/

# OS
.DS_Store
Thumbs.db

# editors
.idea/
.vscode/
*.swp

# проектное
*.log
.coverage
.mypy_cache/

# memory bank — что НЕ пушить
.memory_bank/_claude/SECRETS.md
.memory_bank/business/*.png
.memory_bank/business/*.jpg

# проектная среда Claude (можно оставить и не пушить — на усмотрение)
.claude/settings.local.json
```

## Что в репо ПУШИТСЯ

- Код: `bot.py`, `pipeline.py`, `db.py`, `ai/`, `bot/`, `utils/`
- Конфиг: `pyproject.toml`, `docker-compose.yml`, `Dockerfile`, `.dockerignore`, `.gitignore`
- Документация: `README.md`, `docs/MVP_PROTOTYPE_v4.md`, `.memory_bank/` (кроме `_claude/SECRETS.md`)
- Тесты и скрипты: `scripts/benchmark.py`, `scripts/eval_results.py`
- Ассеты: `assets/tutorial/*.jpg`
- `.env.example` (БЕЗ значений)

## Что в репо НЕ ПУШИТСЯ

- `.env` (реальные токены)
- `.memory_bank/_claude/SECRETS.md` (все токены и URL'ы)
- `data/*.db` (живые данные пользователей)
- `data/test_inspirations/`, `data/test_catalog/`, `data/results/` (внутренние датасеты)

## Workflow

1. Локально работаем в `c:\Users\mycor\aiflatdesigner\`
2. `git init` (один раз)
3. `git add -A; git commit -m "..."; git push`
4. На сервере — `git pull`, `docker compose build && docker compose up -d`

## CI/CD (для MVP — не нужно)

Можно потом добавить GitHub Actions:
- На push в main → SSH в сервер → `git pull && docker compose up -d --build`
- Или manual deploy через secret-actions

На MVP — деплой руками. См. `_claude/DEPLOY.md`.

## Первый push

```bash
cd c:\Users\mycor\aiflatdesigner
git init
git remote add origin git@github.com:julia15535/aiflatdesign.git
git add -A
git commit -m "Initial: project scaffold, memory bank, docs"
git branch -M main
git push -u origin main
```

⚠️ ПЕРЕД `git add -A` убедиться что `.gitignore` корректный — иначе случайно запушим `.env`.

## Если репо НЕ создан на GitHub

Создать через web UI (`https://github.com/new`) → ввести имя `aiflatdesign` → пустой репо (без README) → `git push -u origin main`.

Или через `gh` CLI:

```bash
gh repo create julia15535/aiflatdesign --public --source=. --remote=origin --push
```

## Branches

MVP — работаем на `main`. Никаких feature branches на 7-дневном проекте. После MVP — `main` для prod, `dev` для разработки.
