# Domain: FSM bot states

States машина бота через `aiogram.fsm`. Хранилище — `MemoryStorage` (in-memory; при рестарте бота состояния теряются — пользователь делает /start заново).

## States (GenStates: StatesGroup)

| State | Что ждём | На что переходит |
|---|---|---|
| `onboarding_step_1` | callback `onb:next:2` | `onboarding_step_2` |
| `onboarding_step_2` | callback `onb:next:3` | `onboarding_step_3` |
| `onboarding_step_3` | callback `onb:next:4` | `onboarding_step_4` |
| `onboarding_step_4` | callback `onb:done` | `waiting_scene` |
| `waiting_scene` | message с photo | quality_check → `waiting_room_dims` (или ждём другое фото) |
| `waiting_room_dims` | text (например `5x4` или `не знаю`) | `waiting_target_class` |
| `waiting_target_class` | text (`sofa`, `bed`, …) | `waiting_product_photo` |
| `waiting_product_photo` | message с photo | quality_check → `waiting_product_dims` |
| `waiting_product_dims` | text (например `220x90x85` или `не знаю`) | запуск pipeline |
| `confirming_warning` | callback `size_skip:yes/no` | запуск pipeline или отмена |

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
| Room dims | `5x4`, `5х4`, `5×4`, или `не знаю/skip/нет` | 2 числа, оба в [1, 30] метров |
| Product dims | `220x90x85`, или `не знаю` | 3 числа, все в [5, 1000] см |
| Target class | свободный текст, длина ≤50 | непустое, lower'нутое |

Если формат не парсится — просим переписать, state НЕ меняем.

## Хранение прогресса между шагами

В `FSMContext.update_data(...)` собираем:

```python
{
    "scene_url": str,
    "scene_qc": dict,
    "room_dims": tuple | None,
    "target_class": str,
    "product_url": str,
    "product_qc": dict,
    "product_dims": tuple | None,
    "session_id": int  # после log_session()
}
```

В `confirming_warning` всё это уже есть в state.data — пригодится для повторного pipeline-вызова при `size_skip:yes`.
