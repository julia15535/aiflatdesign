# Handlers (FSM + callbacks)

Стек: aiogram 3.x, `MemoryStorage`. Все handler'ы в `handlers.py` (или прямо в `bot.py` для MVP — допустимо).

## Шаблоны handler'ов

### Photo handler с QC

```python
@dp.message(GenStates.waiting_scene, F.photo)
async def receive_scene(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)

    processed = preprocess_image(file_bytes.read())   # resize 1280 + JPEG
    scene_url = await upload_to_temp_storage(processed)  # 0x0.st

    await message.answer("⏳ Проверяю фото (3 сек)...")
    qc = await check_scene_quality(scene_url)

    if qc.get("recommendation") == "reject":
        await message.answer(f"❌ {qc.get('user_message', 'Не подходит')}")
        return   # state остаётся waiting_scene

    await state.update_data(scene_url=scene_url, scene_qc=qc)

    if qc.get("recommendation") == "warn_user":
        kb = InlineKeyboardBuilder()
        kb.button(text="✓ Всё равно делать", callback_data="qc_scene:proceed")
        kb.button(text="↻ Загрузить другое", callback_data="qc_scene:retry")
        await message.answer(f"⚠️ {qc.get('user_message')}", reply_markup=kb.as_markup())
        return

    await ask_room_dims(message, state)
```

### Text handler с парсингом

```python
@dp.message(GenStates.waiting_room_dims, F.text)
async def receive_room_dims(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    room_dims = None
    if text not in ["не знаю", "skip", "нет"]:
        try:
            parts = text.replace("х", "x").replace("×", "x").split("x")
            room_dims = (float(parts[0]), float(parts[1]))
            if any(d < 1 or d > 30 for d in room_dims):
                raise ValueError
        except (ValueError, IndexError):
            await message.answer("Не понял. Напишите как: 5x4 или 'не знаю'.")
            return
    await state.update_data(room_dims=room_dims)
    await message.answer("Какой объект заменить?\nПримеры: sofa, armchair, bed, lamp, rug.")
    await state.set_state(GenStates.waiting_target_class)
```

### Callback handler

```python
@dp.callback_query(F.data == "qc_scene:proceed")
async def qc_scene_proceed(callback: CallbackQuery, state: FSMContext):
    await ask_room_dims(callback.message, state)
    # await callback.answer()   # подавить "часики" — опционально
```

### Errors

aiogram сам ловит exception в handler'е и пишет в лог. Поверх — общий handler:

```python
@dp.error()
async def errors_handler(event, exception):
    logging.exception("Handler crashed", exc_info=exception)
    # Можем отправить admin'у:
    if ADMIN_TG_ID:
        await bot.send_message(int(ADMIN_TG_ID), f"❌ {type(exception).__name__}: {exception}")
    return True  # пометить exception как обработанное
```

## Запуск pipeline (run_pipeline helper)

```python
async def run_pipeline(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("⏳ Анализирую (10-15 сек)...")
    start_time = time.time()
    try:
        session_id = log_session(
            message.from_user.id,
            data["scene_url"], data["product_url"], data["target_class"],
            data.get("room_dims"), data.get("product_dims"),
            data.get("scene_qc"), data.get("product_qc"), None,
        )
        await state.update_data(session_id=session_id)

        result = await process_user_request(
            scene_url=data["scene_url"],
            product_url=data["product_url"],
            target_class=data["target_class"],
            room_dimensions_m=data.get("room_dims"),
            product_dims_cm=data.get("product_dims"),
            n_seeds=3,
            skip_quality_check=True,   # уже сделали в bot handler'ах
            skip_size_check=(data.get("product_dims") is None),
        )

        if not result["success"] and result.get("error") == "size_mismatch":
            await handle_size_mismatch(message, state, result, data)
            return

        if not result["success"]:
            await message.answer(f"❌ {result.get('message', 'Ошибка')}")
            await state.clear()
            return

        duration = int(time.time() - start_time)
        gen_id = log_generation(session_id, result, duration)
        await send_result(message, result, gen_id, duration)
    except Exception as e:
        logging.exception("Pipeline failed")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")
    await state.clear()
```

## Rating

```python
@dp.callback_query(F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery):
    _, gen_id, rating = callback.data.split(":")
    update_user_rating(int(gen_id), rating)
    await callback.answer(f"Спасибо за оценку: {rating}")
    await callback.message.edit_caption(
        callback.message.caption + f"\n\n📊 Оценка: {rating}",
        reply_markup=None,   # убрать кнопки после голоса
    )
```

## Anti-patterns

- ❌ Long-running операции (`await replicate.async_run(...)`) **внутри** handler'а без предварительного "⏳" сообщения — пользователь думает что бот завис.
- ❌ `time.sleep()` — блокирует event loop. Только `asyncio.sleep()`.
- ❌ Глобальные переменные для session state — используем FSM `state.update_data()`.
- ❌ `bot.send_message(chat_id, ...)` вместо `message.answer(...)` — message сам знает chat_id.
- ❌ Хранить `client = AsyncOpenAI()` в каждом handler'е — глобальный singleton, инициализируется один раз.
