# План: Шаг 3 — Реальная генерация через OpenAI gpt-image-2 (тестовый MVP)

**Статус:** В работе
**Создан:** 2026-05-11
**Последнее обновление:** 2026-05-11

---

## Цель

Заменить заглушку `_finish` в боте на реальную генерацию финального фото через OpenAI gpt-image-2 (один вызов `/v1/images/edits`). Пользователь получает в Telegram готовое фото комнаты со вписанным товаром за 20-30 секунд.

## Контекст

Пользователь убедился (через веб-интерфейс ChatGPT 5.5), что один запрос с фото комнаты + фото товара даёт хороший результат. Принято решение отказаться от Replicate-pipeline и сделать всё через OpenAI gpt-image-2.

Quality=medium ($0.024/картинку), разделить «убрать» и «добавить» на два вопроса.

## Задачи

### А. FSM и диалог

- [ ] `states.py`: заменить `waiting_target_class` на `waiting_to_remove` + `waiting_to_add`
- [ ] `handlers.py`: два вопроса вместо одного, FSM data расширить (to_remove_*, to_add_*)
- [ ] `_run_pre_flight_check` использует to_add_* (то что вписываем)

### Б. Генерация

- [ ] `ai/prompts.py`: добавить `GENERATION_PROMPT` (английский, с акцентом на сохранение визуала и сцены)
- [ ] `ai/generation.py`: функция `generate_room_with_product()` через `client.images.edit(image=[room_bytes, product_bytes], ...)`
- [ ] Скачивание картинок с 0x0.st (URL → bytes) внутри функции
- [ ] Динамический выбор `size` по ориентации фото комнаты (1024x1024 / 1536x1024 / 1024x1536)
- [ ] Fallback на gpt-image-1.5 если gpt-image-2 недоступен

### В. handlers и БД

- [ ] `handlers.py::_finish`: заменить заглушку — генерация + скачивание результата + отправка фото в Telegram
- [ ] Лимит 5/день через `count_recent_generations`
- [ ] `db.py`: добавить колонки `to_remove`, `to_add` в `sessions`; добавить `log_generation()` функцию
- [ ] `.env.example`: добавить `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_QUALITY`, `OPENAI_IMAGE_INPUT_FIDELITY`

### Г. Память проекта

- [ ] Переписать `.memory_bank/ai/generation.md` (gpt-image-2 вместо FLUX)
- [ ] Добавить запись в `.memory_bank/_claude/DECISIONS.md` (отказ от Replicate)
- [ ] Обновить `.memory_bank/_claude/PROJECT-STATE.md` (новый стек)
- [ ] Пометить `.memory_bank/ai/replicate.md` как архив
- [ ] Обновить `.memory_bank/CLAUDE.md` (раздел архитектуры)
- [ ] Обновить `.memory_bank/product_roadmap.md`

### Д. Деплой и тесты

- [ ] Локальная проверка импортов
- [ ] Git commit + push
- [ ] На сервере: git pull, docker compose build, docker compose up -d
- [ ] Тест в Telegram: фото комнаты + убрать «стол» + добавить «диван» + размеры → получить картинку

## Лог выполнения

### 2026-05-11
- План перенесён в `.memory_bank/plans/`
- Проверена сигнатура `openai.images.edit()` в SDK 2.36: принимает массив файлов (bytes), не URL. Размеры фиксированные: 1024x1024, 1536x1024, 1024x1536.
- Начинаю с части А.
