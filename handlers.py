"""Обработчики Telegram-бота.

Шаг 1+2: скелет диалога + проверка качества фото через OpenAI.
Реальная генерация картинки появится в Шагах 3-4.

Подробнее: .memory_bank/bot/handlers.md, .memory_bank/bot/flow.md
"""

from __future__ import annotations

import logging
from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ai.preprocessing import preprocess_image
from ai.quality_check import check_product_quality, check_scene_quality
from db import log_session, touch_user
from states import GenStates
from utils.storage import upload_to_temp_storage

logger = logging.getLogger(__name__)

router = Router()

# --- Парсеры пользовательского ввода ---

_SKIP_WORDS: Final[frozenset[str]] = frozenset({"не знаю", "skip", "нет", "не", "no"})


def _parse_room_dims(text: str) -> tuple[float, float] | None:
    """Парсит '5x4', '5x4', '5×4'. Возвращает None если 'не знаю'. Кидает ValueError при бреде."""
    text = text.strip().lower()
    if text in _SKIP_WORDS:
        return None
    cleaned = text.replace("х", "x").replace("×", "x").replace("*", "x")
    parts = cleaned.split("x")
    if len(parts) != 2:
        raise ValueError("ожидаем два числа через 'x'")
    a, b = float(parts[0]), float(parts[1])
    if not (1 <= a <= 30 and 1 <= b <= 30):
        raise ValueError("размеры должны быть в метрах в диапазоне 1-30")
    return (a, b)


def _parse_product_dims(text: str) -> tuple[float, float, float] | None:
    """Парсит '220x90x85'. Возвращает None если 'не знаю'. Кидает ValueError."""
    text = text.strip().lower()
    if text in _SKIP_WORDS:
        return None
    cleaned = text.replace("х", "x").replace("×", "x").replace("*", "x")
    parts = cleaned.split("x")
    if len(parts) != 3:
        raise ValueError("ожидаем три числа через 'x'")
    dims = tuple(float(p) for p in parts)
    if not all(5 <= d <= 1000 for d in dims):
        raise ValueError("размеры должны быть в см в диапазоне 5-1000")
    return dims  # type: ignore[return-value]


# --- Команды ---


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user:
        touch_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Привет! Я помогу подобрать как мебель из каталога будет смотреться в твоей комнате.\n\n"
        "📷 Загрузи **фото комнаты** (хорошо освещённое, видна большая часть комнаты).\n\n"
        "Команды: /cancel — отменить, /help — подсказка.",
        parse_mode="Markdown",
    )
    await state.set_state(GenStates.waiting_scene)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменил текущий процесс. Команда /start чтобы начать заново.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Я вписываю мебель из фото товара в фото твоей комнаты.\n\n"
        "Шаги:\n"
        "1. Фото комнаты\n"
        "2. Размеры комнаты в метрах (например 5x4) или 'не знаю'\n"
        "3. Что заменить (sofa / armchair / bed / lamp / ...)\n"
        "4. Фото товара (на белом фоне как в каталоге)\n"
        "5. Размеры товара в см (например 220x90x85) или 'не знаю'\n\n"
        "Команды: /start — начать, /cancel — отменить.",
    )


# --- Получение фото комнаты ---


async def _download_photo(bot: Bot, message: Message) -> bytes:
    """Скачать самое большое разрешение присланного фото."""
    if not message.photo:
        raise ValueError("в сообщении нет фото")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    if not file.file_path:
        raise ValueError("не получили file_path от Telegram")
    buf = await bot.download_file(file.file_path)
    if buf is None:
        raise ValueError("Telegram вернул пустой файл")
    return buf.read()


def _kb_qc_warn(prefix: str) -> InlineKeyboardBuilder:
    """Клавиатура [Всё равно делать] / [Загрузить другое] для QC warn_user."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Всё равно делать", callback_data=f"qc:{prefix}:proceed")
    kb.button(text="🔄 Загрузить другое", callback_data=f"qc:{prefix}:retry")
    kb.adjust(2)
    return kb


@router.message(GenStates.waiting_scene, F.photo)
async def receive_scene(message: Message, state: FSMContext, bot: Bot) -> None:
    await message.answer("⏳ Проверяю фото (3-5 секунд)...")
    try:
        image_bytes = await _download_photo(bot, message)
        processed = preprocess_image(image_bytes)
        scene_url = await upload_to_temp_storage(processed, filename="scene.jpg")
    except Exception:
        logger.exception("Не удалось скачать/загрузить фото комнаты")
        await message.answer("❌ Не получилось загрузить фото. Попробуй ещё раз.")
        return

    qc = await check_scene_quality(scene_url)
    rec = qc.get("recommendation", "proceed")
    user_msg = qc.get("user_message") or ""

    await state.update_data(scene_url=scene_url, scene_qc=qc)

    if rec == "reject":
        await message.answer(f"❌ {user_msg or 'Это фото не подходит для интерьера.'}\n\nЗагрузи другое.")
        return  # state остаётся waiting_scene

    if rec == "warn_user":
        kb = _kb_qc_warn("scene")
        await message.answer(
            f"⚠️ {user_msg or 'Фото получилось не очень — качество результата может пострадать.'}\n\nЧто делаем?",
            reply_markup=kb.as_markup(),
        )
        return  # переход внутри callback

    await _ask_room_dims(message, state)


@router.callback_query(F.data == "qc:scene:proceed")
async def qc_scene_proceed(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await _ask_room_dims(callback.message, state)


@router.callback_query(F.data == "qc:scene:retry")
async def qc_scene_retry(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("Жду новое фото комнаты.")


# --- Размеры комнаты ---


async def _ask_room_dims(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✓ Сцена принята.\n\n"
        "📐 Размеры комнаты в метрах? Формат `длинаxширина`, например `5x4`.\n"
        "Если не знаешь — напиши `не знаю`.",
        parse_mode="Markdown",
    )
    await state.set_state(GenStates.waiting_room_dims)


@router.message(GenStates.waiting_room_dims, F.text)
async def receive_room_dims(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    try:
        room_dims = _parse_room_dims(message.text)
    except ValueError:
        await message.answer(
            "Не понял формат. Напиши как `5x4` (два числа через `x`) или `не знаю`.",
            parse_mode="Markdown",
        )
        return
    await state.update_data(room_dims=room_dims)
    await _ask_target_class(message, state)


# --- Объект для замены ---


async def _ask_target_class(message: Message, state: FSMContext) -> None:
    await message.answer(
        "🛋 Что заменить в комнате?\n\n"
        "Напиши на английском, например: `sofa`, `armchair`, `bed`, `lamp`, `coffee table`, `wardrobe`, `rug`.",
        parse_mode="Markdown",
    )
    await state.set_state(GenStates.waiting_target_class)


@router.message(GenStates.waiting_target_class, F.text)
async def receive_target_class(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    target = message.text.strip().lower()
    if not target or len(target) > 50:
        await message.answer("Не понял. Напиши проще: `sofa`, `armchair`, `lamp`.", parse_mode="Markdown")
        return
    await state.update_data(target_class=target)
    await message.answer(
        f"✓ Заменяем: **{target}**\n\n"
        "📷 Загрузи **фото товара** (как в каталоге Hoff/WB/Ozon — на белом фоне, один предмет).",
        parse_mode="Markdown",
    )
    await state.set_state(GenStates.waiting_product_photo)


# --- Фото товара ---


@router.message(GenStates.waiting_product_photo, F.photo)
async def receive_product_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    await message.answer("⏳ Проверяю фото товара (3-5 секунд)...")
    try:
        image_bytes = await _download_photo(bot, message)
        processed = preprocess_image(image_bytes)
        product_url = await upload_to_temp_storage(processed, filename="product.jpg")
    except Exception:
        logger.exception("Не удалось скачать/загрузить фото товара")
        await message.answer("❌ Не получилось загрузить фото. Попробуй ещё раз.")
        return

    qc = await check_product_quality(product_url)
    rec = qc.get("recommendation", "proceed")
    user_msg = qc.get("user_message") or ""

    await state.update_data(product_url=product_url, product_qc=qc)

    if rec == "reject":
        await message.answer(f"❌ {user_msg or 'Это фото не похоже на товар.'}\n\nЗагрузи другое.")
        return

    if rec == "warn_user":
        kb = _kb_qc_warn("product")
        await message.answer(
            f"⚠️ {user_msg or 'Фото товара так себе — результат может пострадать.'}\n\nЧто делаем?",
            reply_markup=kb.as_markup(),
        )
        return

    await _ask_product_dims(message, state)


@router.callback_query(F.data == "qc:product:proceed")
async def qc_product_proceed(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await _ask_product_dims(callback.message, state)


@router.callback_query(F.data == "qc:product:retry")
async def qc_product_retry(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("Жду новое фото товара.")


# --- Размеры товара ---


async def _ask_product_dims(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✓ Товар принят.\n\n"
        "📐 Размеры товара в сантиметрах? Формат `длинаxглубинаxвысота`, например `220x90x85`.\n"
        "Если не знаешь — напиши `не знаю`.",
        parse_mode="Markdown",
    )
    await state.set_state(GenStates.waiting_product_dims)


@router.message(GenStates.waiting_product_dims, F.text)
async def receive_product_dims(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    try:
        product_dims = _parse_product_dims(message.text)
    except ValueError:
        await message.answer(
            "Не понял формат. Напиши как `220x90x85` (три числа через `x`) или `не знаю`.",
            parse_mode="Markdown",
        )
        return
    await state.update_data(product_dims=product_dims)
    await _finish(message, state)


# --- Финал (заглушка генерации) ---


async def _finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = message.from_user.id if message.from_user else 0

    session_id = log_session(
        tg_user_id=user_id,
        scene_url=data.get("scene_url"),
        product_url=data.get("product_url"),
        target_class=data.get("target_class"),
        room_dims_m=data.get("room_dims"),
        product_dims_cm=data.get("product_dims"),
        scene_quality=data.get("scene_qc"),
        product_quality=data.get("product_qc"),
    )

    await message.answer(
        "✨ Принял всё что нужно!\n\n"
        f"📋 Сессия #{session_id} записана в базу.\n\n"
        "🚧 **На этом этапе (Шаг 1+2) генерация картинки ещё не реализована** — это будет в Шагах 3-4.\n"
        "Пока проверяем что весь диалог работает и фильтр плохих фото корректен.\n\n"
        "Команда /start чтобы прогнать ещё один сценарий.",
        parse_mode="Markdown",
    )
    await state.clear()


# --- Неподходящий контент в неправильном state ---


@router.message(GenStates.waiting_scene)
async def waiting_scene_other(message: Message) -> None:
    await message.answer("Сейчас жду **фото** комнаты, а не текст. Загрузи фото.", parse_mode="Markdown")


@router.message(GenStates.waiting_product_photo)
async def waiting_product_other(message: Message) -> None:
    await message.answer("Сейчас жду **фото** товара. Загрузи фото.", parse_mode="Markdown")
