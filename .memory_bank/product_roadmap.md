# Product Roadmap — MVP

План на 6-8 дней. Каждый день имеет конкретный чек точки готовности.

Источник правды: [`docs/MVP_PROTOTYPE_v4.md`](../docs/MVP_PROTOTYPE_v4.md), раздел "Implementation roadmap".

## День 1 — Скаффолд + базовый бот + БД

- [ ] Структура папок (`bot.py`, `db.py`, `ai/`, `utils/`, `data/`, `scripts/`)
- [ ] `pyproject.toml` с зависимостями (aiogram 3, openai≥1.50, replicate, Pillow, numpy, opencv-python, scikit-image, httpx, python-dotenv)
- [ ] `.env.example` (без реальных токенов)
- [ ] `db.py` со схемой users / sessions / generations (см. `domain/data_model.md`)
- [ ] `bot.py` с FSM states (БЕЗ онбординга и quality check пока — голый скелет)
- [ ] `utils/storage.py` для 0x0.st (upload + delete by id)
- [ ] `ai/preprocessing.py` (resize до 1280px по длинной стороне)
- [ ] Локальный запуск, базовый flow без AI

**Чек дня 1**: бот принимает данные через все шаги FSM, всё пишет в БД.

## День 2 — Quality Check + Scene Analysis

- [ ] `ai/quality_check.py` (два промпта: scene и product)
- [ ] `ai/scene_analysis.py` (GPT-5.4 Mini vision + GroundedSAM для slot mask)
- [ ] Интеграция quality check в bot.py с FSM-обработкой warn/reject
- [ ] Тест на 5-10 фото разного качества

**Чек дня 2**: бот корректно отклоняет не-интерьеры, предупреждает о тёмных/искажённых фото.

## День 3 — Pre-flight Size Check + Generation skeleton

- [ ] `ai/size_check.py` (вся геометрия: bbox → реальные см)
- [ ] `utils/geometry.py` (IoU, helpers)
- [ ] Логика 4 вердиктов: perfect / acceptable / marginal / doesnt_fit
- [ ] Обработка кейса в bot.py с кнопками ["Всё равно делать", "Загрузить другой"]
- [ ] Скелет `ai/generation.py` (один Fill Pro вызов, без best-of-N)
- [ ] Тест: один Fill Pro вызов end-to-end работает

**Чек дня 3**: бот отклоняет диван 350 см в 2.5-метровую комнату, генерит для нормальных кейсов.

## День 4 — Best-of-N + Validation + Upscale

- [ ] Multi-seed (3 параллельных Fill Pro через asyncio.gather)
- [ ] `ai/validation.py` (CLIP-I, presence через Grounding DINO, SSIM)
- [ ] WOW score формула (см. `ai/validation.md`)
- [ ] Best-pick logic (sort by WOW score)
- [ ] `ai/upscaling.py` (Clarity Upscaler, опциональный)
- [ ] Полный pipeline end-to-end

**Чек дня 4**: бот возвращает best-of-3 с метриками за ~75 сек.

## День 5 — Тестовый датасет + benchmark

- [ ] Собрать 30 inspiration-фото (10 easy / 15 medium / 5 hard) — `data/test_inspirations/`
- [ ] Собрать 20 catalog-фото с размерами в имени (например `sofa_220x90x85_brown.jpg`) — `data/test_catalog/`
- [ ] `scripts/benchmark.py` — прогон по датасету, вывод сводной таблицы
- [ ] Записать результаты в `business/benchmark_results.md`

**Чек дня 5**: получены реальные данные, видны failure cases.

## День 6 — Visual assets онбординга

⭐ **Ключевой день — без assets онбординг не работает.**

- [ ] Claude Code предлагает 3 подхода для assets и ждёт выбор пользователя:
  - **A**: Готовые из Unsplash + надписи в Pillow (час работы, бесплатно)
  - **B**: Сгенерить FLUX'ом по описаниям + подобрать (~$0.40, быстро)
  - **C**: Композиты из реальных скриншотов в Figma (час, лучшее качество)
- [ ] Создание 4 финальных ассетов в `assets/tutorial/`:
  - `01_intro.jpg` — до/после
  - `02_scene_good_bad.jpg` — примеры сцен ✅/❌
  - `03_product_good_bad.jpg` — примеры товаров ✅/❌
  - `04_size_help.jpg` — как мерить
- [ ] Реализация полного онбординга в bot.py (callback'и, FSM)
- [ ] `is_user_onboarded` / `mark_user_onboarded` в `db.py`
- [ ] Команды `/start`, `/help`, `/cancel`, `/myhistory`

**Чек дня 6**: пройди туториал глазами свежего пользователя — понятно?

## День 7 — Beta-тест + полировка

- [ ] Дать бота 3-5 знакомым дизайнерам и/или маркетологу Hoff/Divan
- [ ] Просить пройти полный flow без подсказок
- [ ] Собрать обратную связь и оценки в `business/beta_feedback.md`
- [ ] Финальная сводка: WOW score, success rate, user rating, cost

**Чек дня 7**: 30-50 живых регенераций, готово Go/No-go решение.

## День 8 (опционально) — Tweaks по фидбэку

- [ ] Подгонка промптов под частые failure cases
- [ ] Возможно: добавить fallback на Kontext Pro для simple scenes (cheap path)
- [ ] Дополнительные tooltips в боте

## Текущий статус

**Дата старта**: 2026-05-11
**Дата сейчас**: 2026-05-11
**День**: 0 (подготовка — memory bank, доступы, токены)

Незавершённых планов в `plans/` нет.
