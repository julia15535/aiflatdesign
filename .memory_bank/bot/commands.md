# Bot commands

Минимальный набор для MVP. `/start`, `/help`, `/cancel`, `/myhistory`.

## /start

```python
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if not is_user_onboarded(message.from_user.id):
        await show_onboarding_step_1(message, state)
    else:
        await message.answer("👋 С возвращением!\n\nЗагрузите фото комнаты...")
        await state.set_state(GenStates.waiting_scene)
```

Логика:
- Первый раз — туториал из 4 экранов
- Повторный — сразу `waiting_scene`

## /help

```python
@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await show_onboarding_step_1(message, state)
```

Туториал заново для любого пользователя.

## /cancel

```python
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. Команда /start чтобы начать заново.")
```

Сброс state. Не очищает БД, только FSM.

## /myhistory

```python
@dp.message(Command("myhistory"))
async def cmd_history(message: Message):
    rows = get_recent_generations(message.from_user.id, limit=5)
    if not rows:
        await message.answer("У вас пока нет генераций.")
        return
    for row in rows:
        await message.answer_photo(
            row["result_url"],
            caption=f"WOW: {row['wow_score']:.2f}\n{row['target_class']}\n{row['created_at']}"
        )
```

Возвращает последние 5 успешных генераций пользователя в чат. Для сравнения регенов и UX'а.

⚠️ MVP-вариант: без пагинации, без удаления. Если у пользователя 100 генераций — показываем только последние 5.

## BotFather setup

В @BotFather:

```
Bot Name: AI Flat Designer
Bot Username: <получим при регистрации>
Description: Telegram-бот, который вписывает мебель из каталожных фото в фото вашей комнаты. AI сохраняет точный товар (цвет, форма, паттерн).
About: Виртуальный примерочный для мебели и декора.

Commands:
start - Начать или вернуться к боту
help - Показать инструкцию
cancel - Отменить текущий процесс
myhistory - Последние 5 регенераций
```

## Лимит регенераций

В обработчике `waiting_scene` (и/или перед запуском pipeline):

```python
recent_count = get_generations_count_24h(message.from_user.id)
if recent_count >= 5:
    await message.answer(
        "Дневной лимит 5 генераций исчерпан. Возвращайтесь завтра!"
    )
    await state.clear()
    return
```

## /admin (не для MVP)

В прототипе не делаем. Когда понадобится — добавить через проверку `ADMIN_TG_ID`:

```python
if message.from_user.id == int(os.environ["ADMIN_TG_ID"]):
    # admin commands: /stats, /reset_user, /export_csv, ...
```

## Anti-patterns

- ❌ `/about`, `/info`, `/contact` — лишние команды для MVP.
- ❌ Аргументы команд (`/start NEW_FLOW`) — путают пользователей.
- ❌ Кастомные команды на каждый target_class — есть один flow, и его достаточно.
- ❌ Inline-режим — это не reusable inline bot.
