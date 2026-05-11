# План: Шаг 1+2 — Скелет бота + проверка качества фото

**Статус:** В работе
**Создан:** 2026-05-11
**Последнее обновление:** 2026-05-11

---

## Цель

Запустить на сервере работающий Telegram-бот, который:
- Откликается на /start, проводит пользователя по всем шагам диалога (фото комнаты → размеры → объект → фото товара → размеры)
- Проверяет качество фото через OpenAI (плохие отклоняет, спорные предупреждает, хорошие пропускает)
- Сохраняет сессии в SQLite базу данных
- В конце пока пишет "тут будет картинка" — генерации нет (Шаг 3-4)

## Контекст

После Шага 0: память проекта полная, git репозиторий есть, на сервере склонирован код. Пользователь выбрал объединить Шаги 1+2 в один заход чтобы сразу видеть работу OpenAI. Менеджер пакетов — uv. Цикл работы: локально → git push → server git pull.

## Задачи

### А. Подготовка локально

- [ ] Создать `pyproject.toml` со списком зависимостей (aiogram, openai≥1.50, replicate, Pillow, numpy, opencv-python-headless, httpx, python-dotenv, scikit-image)
- [ ] Создать `.env.example` — шаблон без значений
- [ ] Создать пустые папки `ai/`, `utils/`, `data/`
- [ ] Проверить или установить uv локально
- [ ] `uv venv` + `uv pip install -e .` — создать виртуальное окружение и поставить зависимости

### Б. База данных

- [ ] Написать `db.py`: init_db, log_session, is_user_onboarded, mark_user_onboarded
- [ ] Локально проверить что `data/prototype.db` создаётся без ошибок

### В. Подключение OpenAI

- [ ] `ai/prompts.py` — два промпта (scene quality, product quality) из `.memory_bank/ai/prompts.md`
- [ ] `ai/preprocessing.py` — `preprocess_image(bytes) -> bytes` (ресайз до 1280 по большей стороне)
- [ ] `utils/storage.py` — `upload_to_temp_storage(bytes) -> str` через 0x0.st
- [ ] `ai/quality_check.py` — клиент OpenAI с base_url, функции check_scene_quality / check_product_quality, fallback на proceed при ошибках
- [ ] `scripts/test_quality_check.py` — локальный тест на 2-3 картинках

### Г. Скелет бота

- [ ] `states.py` — FSM состояния по `domain/states.md`
- [ ] `handlers.py` — обработчики /start, фото сцены, размеры комнаты, target_class, фото товара, размеры товара
- [ ] `bot.py` — оркестратор с загрузкой .env, Bot, Dispatcher, polling

### Д. Запуск на сервере

- [ ] `Dockerfile` (multi-stage, python:3.11-slim, opencv-headless, non-root)
- [ ] `docker-compose.yml` (отдельная сеть, volume для data, host.docker.internal, без портов)
- [ ] `.dockerignore`
- [ ] git push на Github
- [ ] На сервере: git pull, создать .env с реальными секретами (chmod 600), docker compose build + up
- [ ] Проверить логи: бот стартовал, polling работает

### Е. Тестирование

- [ ] Сценарий 1: хорошее фото комнаты + хорошее фото товара → дойти до "тут будет картинка"
- [ ] Сценарий 2: тёмное фото → должно выдать предупреждение
- [ ] Сценарий 3: не-интерьер → должен отказать
- [ ] Показать скриншоты пользователю — финальная сверка диалога

## Лог выполнения

### 2026-05-11
- План перенесён из временного места в `.memory_bank/plans/`
- Начинаю с Части А
