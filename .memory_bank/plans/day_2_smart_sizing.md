# План: Шаг 2.5 — Умный сбор размеров + предварительная оценка влезет ли товар

**Статус:** В работе
**Создан:** 2026-05-11
**Последнее обновление:** 2026-05-11

---

## Цель

Заменить жёсткий формат сбора размеров комнаты (`5x4`) на естественный («Часть гостиной 18м², потолки 270см»). Объекты спрашивать на русском. После размеров товара — пред-полётная проверка влезет ли он в место через OpenAI vision. Если впишется молча идём дальше, если на грани — спрашиваем, если не влезает — говорим переразмерить.

## Контекст

Текущий диалог жёстко требует «5x4» в метрах. На практике пользователь фотографирует часть комнаты (см. пример с эркером), полная не в кадре, замерить нечем. Высота потолка + описание словами — реалистичный ввод. Объекты на английском не подходят русскому боту.

Главная новизна — pre-flight check ДО генерации (которой пока нет, но появится в Шаге 3-4). ИИ оценивает место по фото с потолком как масштабным референсом, сравнивает с размерами товара, даёт вердикт fits/marginal/doesnt_fit.

## Задачи

### А. Маппинг объектов

- [ ] Создать `ai/object_mapping.py` со словарём ~20 типичных предметов (диван→sofa, кресло→armchair, обеденный стол→dining table, ...)
- [ ] Функция `to_english(ru: str) -> tuple[str, str]` возвращает (english, canonical_ru, is_known)

### Б. Промпт и scene_analysis

- [ ] Добавить `SLOT_ESTIMATION_PROMPT` в `ai/prompts.py`
- [ ] Создать `ai/scene_analysis.py` с `estimate_slot_dimensions(scene_url, target_en, target_ru, ceiling_cm, room_description) -> dict`
- [ ] Fallback при ошибке: дефолты по типу объекта + confidence=low
- [ ] `scripts/test_slot_estimation.py` для локальной отладки

### В. Сравнение и решение

- [ ] Создать `ai/size_check.py` с `compare_product_to_slot(product_dims_cm, slot_dims, tolerance_pct=20)`
- [ ] Вердикты: fits_ok (≤10%), marginal (10-25%), doesnt_fit (>25%)
- [ ] Учитывать confidence из оценки слота (low → +10% к tolerance)

### Г. FSM и обработчики

- [ ] `states.py`: заменить `waiting_room_dims` на `waiting_room_info`, добавить `confirming_size_mismatch`
- [ ] `handlers.py::_parse_room_info(text)` — парсит «потолок 270см, часть гостиной 18м²»
- [ ] `_ask_room_info` вместо `_ask_room_dims` (одно сообщение с примерами)
- [ ] `_ask_target_class` — на русском с примерами «диван, кресло, обеденный стол»
- [ ] `receive_target_class` — нормализация через `object_mapping.to_english()`
- [ ] `_run_pre_flight_check` — оценка слота + сравнение + 3 ветки
- [ ] Callback-обработчики `size:proceed`, `size:retry`

### Д. БД

- [ ] Расширить `db.log_session(...)` параметрами ceiling_height_cm, room_description, slot_estimation, size_check
- [ ] Добавить столбцы в `sessions` через `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` через try/except для существующей БД

### Е. Память проекта

- [ ] Обновить `.memory_bank/domain/states.md`
- [ ] Переписать `.memory_bank/bot/flow.md`
- [ ] Дополнить `.memory_bank/ai/scene_analysis.md`
- [ ] Дополнить `.memory_bank/ai/size_check.md`
- [ ] Дополнить `.memory_bank/ai/prompts.md` (добавить SLOT_ESTIMATION)
- [ ] Создать `.memory_bank/ai/object_mapping.md`
- [ ] Создать `.memory_bank/business/backlog_post_mvp.md` (зафиксировать идею с 5-10 фото)

### Ж. Деплой и тесты

- [ ] Локальная проверка импортов
- [ ] Git commit + push
- [ ] На сервере: git pull, docker compose build, docker compose up -d
- [ ] Тест 1 (впишется): фото + потолок 270 + обеденный стол + 100x70x76 → молча
- [ ] Тест 2 (на грани): то же + 140x90x76 → кнопки
- [ ] Тест 3 (не влезет): то же + 200x120x76 → говорит «не влезет»

## Решения принятые пользователем (2026-05-11)

- Высота потолка обязательна (не «не знаю»)
- Описание комнаты вместе с потолком в одном вопросе
- На грани (10-25%) → кнопки для пользователя
- Впишется → молча идём в генерацию (пока заглушка)
- Идея «5-10 фото по кругу» → отложена в backlog для после-MVP

## Лог выполнения

### 2026-05-11
- План перенесён из временного места в `.memory_bank/plans/`
- Начинаю с Части А (объектный маппинг)
