# Domain: FSM bot states

States машина бота через `aiogram.fsm`. Хранилище — `MemoryStorage` (in-memory; при рестарте бота состояния теряются — пользователь делает /start заново).

## States (GenStates: StatesGroup)

| State | Что ждём | На что переходит |
|---|---|---|
| `onboarding_step_1..4` | callback кнопок туториала | следующий шаг туториала / `waiting_scene` (Шаг 6) |
| `waiting_scene` | message с photo | quality_check → `waiting_room_info` (или ждём другое фото) |
| `waiting_room_info` | text «потолок 270см, часть гостиной 18м²» | парсинг → `waiting_target_class` |
| `waiting_target_class` | text на русском («диван», «обеденный стол», …) | маппинг RU→EN → `waiting_product_photo` |
| `waiting_product_photo` | message с photo | quality_check → `waiting_product_dims` |
| `waiting_product_dims` | text (например `220x90x85` или `не знаю`) | pre-flight check → `confirming_size_mismatch` (если на грани/не влезает) или сразу финал |
| `confirming_size_mismatch` | callback `size:proceed` / `size:retry` | финал или сброс |

## Ключевые правила

- **При /start без онбординга** (пользователь онбоарден ранее) — сразу `waiting_scene`.
- **При /help** — туториал заново (показать онбординг даже онбоарженным).
- **При /cancel** — `state.clear()`, всё начнётся с /start.
- **Если QC=reject** — состояние НЕ меняется, пользователь грузит другое фото в тот же state.
- **Если QC=warn_user** — показываем inline-кнопки `[✓ Всё равно делать]` / `[↻ Загрузить другое]`; обработчики callback'ов:
  - `qc_scene:proceed` → перейти в `waiting_room_dims`
  - `qc_scene:retry` → остаться в `waiting_scene`
  - `qc_product:proceed` → перейти в `waiting_product_dims`
  - `qc_product:retry` → остаться в `waiting_product_photo`
- **При size_mismatch** — переход в `confirming_warning`, ждём callback:
  - `size_skip:yes` → запуск pipeline с `skip_size_check=True`
  - `size_skip:no` → `state.clear()` + "Отменил"
- **После успешной генерации** — `state.clear()`. Пользователь начинает заново с /start.

## Парсинг user input

| Поле | Формат | Валидация |
|---|---|---|
| Room info | произвольный текст с фразой «N см / N м» где-то внутри | regex `\d+(\.\d+)?\s*(см|cm|мм|mm|м|m|метров|метра|метр)`, потолок 150-500 см после нормализации; иначе бот переспрашивает |
| Product dims | `220x90x85`, или `не знаю` | 3 числа, все в [5, 1000] см |
| Target class | свободный текст на русском, длина ≤60 | через `ai/object_mapping.to_english()`; если не нашли — предупреждаем, но идём дальше |

Если формат не парсится — просим переписать, state НЕ меняем.

## Хранение прогресса между шагами

В `FSMContext.update_data(...)` собираем:

```python
{
    "scene_url": str,
    "scene_qc": dict,
    "ceiling_cm": int,            # высота потолка в см
    "room_description": str,      # текстовое описание комнаты
    "target_en": str,             # английское название для промптов/Replicate
    "target_ru": str,             # каноническое русское для UI
    "target_known": bool,         # нашли ли в словаре object_mapping
    "product_url": str,
    "product_qc": dict,
    "product_dims": tuple | None,
    "slot": dict | None,          # результат estimate_slot_dimensions
    "size_check": dict | None,    # результат compare_product_to_slot
}
```

В `confirming_warning` всё это уже есть в state.data — пригодится для повторного pipeline-вызова при `size_skip:yes`.
