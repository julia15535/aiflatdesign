# План: Шаг 3.5 — Двухфазная генерация с промежуточным подтверждением размеров

**Статус:** В работе
**Создан:** 2026-05-11
**Последнее обновление:** 2026-05-11

---

## Цель

Перестроить pipeline под двухфазную модель: сначала удаление + показ размеров для подтверждения, потом финальная вставка товара. Убрать словарь объектов, использовать свободный текст. Починить retry при скачивании.

## Контекст

Жалобы пользователя:
1. Словарь не понимает «убрать стулья, диван и пол почистить» — распознаёт только «диван»
2. Ошибка `Server disconnected` при скачивании с 0x0.st
3. Хочет промежуточный шаг с показом размеров до финальной генерации

Подтверждённые решения:
- Свободный текст вместо словаря
- gpt-image-2 рисует цифры на промежуточной картинке + мы дублируем текстом из vision-оценки
- Размеры товара спрашиваем как сейчас
- Retry 3 раза + fallback на catbox.moe при скачивании

## Задачи

### А. Скачивание

- [ ] `utils/storage.py`: helper `download_with_retry(url)` — 3 попытки с задержками 1с/2с/4с
- [ ] `ai/generation.py`: использовать helper для скачивания

### Б. Vision-оценка свободного места

- [ ] Промпт `SLOT_AFTER_REMOVAL` в `ai/prompts.py`
- [ ] Функция `estimate_post_removal_slot()` в `ai/scene_analysis.py`

### В. Этап А — генерация с размерами

- [ ] Промпт `REMOVAL_WITH_DIMENSIONS` в `ai/prompts.py`
- [ ] Функция `generate_removal_with_dimensions()` в `ai/generation.py`
- [ ] В handlers.py — последовательно: vision-оценка → image edit

### Г. FSM подтверждение

- [ ] `states.py`: `confirming_slot_dimensions`, `editing_slot_dimensions`
- [ ] `handlers.py`: callbacks `slot:confirm`, `slot:edit`; парсинг текстовых правок

### Д. Этап Б — финальная генерация

- [ ] Переписать `GENERATION` промпт — на русском, без `_en` параметров
- [ ] Переписать `generate_room_with_product()` — использовать `to_remove`, `to_add_with_placement`, готовый `final_slot_dims`

### Е. Чистка словаря

- [ ] Удалить `ai/object_mapping.py`
- [ ] Удалить импорты `to_english`, `known_examples` из handlers.py
- [ ] Удалить `.memory_bank/ai/object_mapping.md` или пометить deprecated

### Ж. Память проекта

- [ ] DECISIONS.md: отказ от словаря + двухфазная генерация
- [ ] bot/flow.md: переписать новый flow
- [ ] ai/generation.md: добавить новые функции
- [ ] _claude/PROJECT-STATE.md: фаза = Шаг 3.5

### З. Деплой

- [ ] Локальная проверка импортов
- [ ] Git commit + push
- [ ] На сервере: git pull → docker compose build → up
- [ ] Тест в Telegram

## Лог выполнения

### 2026-05-11
- План перенесён из временного места
- Начинаю с части А (retry для скачивания)
