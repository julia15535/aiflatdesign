"""Обработчики Telegram-бота.

Шаги 1+2+2.5: скелет диалога + проверка качества фото + pre-flight оценка
размеров места под товар через OpenAI vision.

Реальная генерация картинки появится в Шагах 3-4.

Подробнее: .memory_bank/bot/handlers.md, .memory_bank/bot/flow.md
"""

from __future__ import annotations

import logging
import re
from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ai.generation import generate_removal_with_dimensions, generate_room_with_product
from ai.preprocessing import preprocess_image
from ai.quality_check import check_product_quality, check_scene_quality
from ai.scene_analysis import estimate_post_removal_slot
from ai.size_check import compare_product_to_slot
from db import count_recent_generations, log_generation, log_session, touch_user
from states import GenStates
from utils.storage import upload_to_temp_storage

DAILY_GENERATION_LIMIT = 5

logger = logging.getLogger(__name__)

router = Router()

# --- Парсеры пользовательского ввода ---

_SKIP_WORDS: Final[frozenset[str]] = frozenset({"не знаю", "skip", "нет", "не"})

# Регулярки для извлечения высоты потолка из произвольного текста.
# Захватываем число (целое или дробное) + единицу (см|cm|м|m|мм|mm|метров|метра|метр).
_CEILING_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(см|cm|мм|mm|метров|метра|метр|м|m)\b",
    re.IGNORECASE,
)


def _parse_ceiling_height(text: str) -> int | None:
    """Извлечь высоту потолка из произвольного текста.

    Возвращает высоту в см. Если не нашли — None.
    """
    matches = _CEILING_RE.findall(text)
    if not matches:
        return None
    # Берём первое совпадение. Если их несколько (напр. «250см и стены 4м»)
    # — берём первое, потому что оно скорее всего про потолок (фраза начинается с него)
    num_str, unit = matches[0]
    num = float(num_str.replace(",", "."))
    unit_lower = unit.lower()
    if unit_lower in ("см", "cm"):
        cm = num
    elif unit_lower in ("мм", "mm"):
        cm = num / 10
    else:  # м, m, метров, метра, метр
        cm = num * 100
    cm_int = int(round(cm))
    # Sanity check: потолок 150-500 см
    if not (150 <= cm_int <= 500):
        return None
    return cm_int


def _parse_room_info(text: str) -> tuple[int, str]:
    """Парсит ответ «опиши комнату и потолок одним сообщением».

    Returns:
        (ceiling_cm, room_description) — описание = исходный текст без потолка-фразы.

    Raises:
        ValueError: если потолок не нашли.
    """
    ceiling_cm = _parse_ceiling_height(text)
    if ceiling_cm is None:
        raise ValueError("высота потолка не найдена")
    # Описание = исходный текст. Не вычищаем фразу про потолок — это контекст для ИИ.
    description = text.strip()
    return ceiling_cm, description


def _parse_product_dims(text: str) -> tuple[float, float, float] | None:
    """Парсит '220x90x85'. Возвращает None если 'не знаю'. Кидает ValueError при бреде."""
    text = text.strip().lower()
    if text in _SKIP_WORDS:
        return None
    cleaned = text.replace("х", "x").replace("×", "x").replace("*", "x").replace(" ", "")
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
        "Привет! Я подбираю как мебель из каталога будет смотреться в твоей комнате.\n\n"
        "Загрузи фото комнаты (нормальное освещение, видна большая часть).\n\n"
        "Команды: /cancel — отменить, /help — подсказка.",
    )
    await state.set_state(GenStates.waiting_scene)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменил. Команда /start чтобы начать заново.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Я вписываю мебель в фото твоей комнаты. Шаги:\n\n"
        "1. Фото комнаты\n"
        "2. Описание комнаты и высота потолка (например «часть гостиной 18м², потолки 270см»)\n"
        "3. Какой объект заменить (например «обеденный стол»)\n"
        "4. Фото товара (как в каталоге — на белом фоне)\n"
        "5. Размеры товара в см (например 140x90x76)\n\n"
        "Дальше я прикину влезет ли товар и запущу подбор картинки.\n\n"
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
        return

    if rec == "warn_user":
        kb = _kb_qc_warn("scene")
        await message.answer(
            f"⚠️ {user_msg or 'Фото получилось не очень — качество результата может пострадать.'}\n\nЧто делаем?",
            reply_markup=kb.as_markup(),
        )
        return

    await _ask_room_info(message, state)


@router.callback_query(F.data == "qc:scene:proceed")
async def qc_scene_proceed(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await _ask_room_info(callback.message, state)


@router.callback_query(F.data == "qc:scene:retry")
async def qc_scene_retry(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("Жду новое фото комнаты.")


# --- Описание комнаты + потолок ---


async def _ask_room_info(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✓ Сцена принята.\n\n"
        "Опиши комнату и высоту потолка одним сообщением.\n\n"
        "Примеры:\n"
        "• «Часть гостиной около 18м², потолки 270см»\n"
        "• «Спальня 12м², потолок 250см, фото половина комнаты»\n"
        "• «Кухня-студия в новостройке, потолки 2.7 метра»\n\n"
        "Высота потолка нужна обязательно — это масштаб для оценки размеров. "
        "В обычных квартирах ~270см, в хрущёвках 250см, в сталинках 300-320см."
    )
    await state.set_state(GenStates.waiting_room_info)


@router.message(GenStates.waiting_room_info, F.text)
async def receive_room_info(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    try:
        ceiling_cm, description = _parse_room_info(message.text)
    except ValueError:
        await message.answer(
            "Не нашёл высоту потолка в твоём сообщении. Напиши прямо число с единицей: «270см» или «2.7м».\n"
            "Можно вместе с описанием, например: «Часть гостиной 18м², потолки 270см»."
        )
        return
    await state.update_data(ceiling_cm=ceiling_cm, room_description=description)
    await message.answer(f"✓ Понял: потолок {ceiling_cm}см.")
    await _ask_to_remove(message, state)


# --- Что убрать и что добавить (свободный текст, без словаря) ---


async def _ask_to_remove(message: Message, state: FSMContext) -> None:
    await message.answer(
        "🗑 Что УБРАТЬ из комнаты?\n\n"
        "Опиши свободно. Можно несколько вещей. Например:\n"
        "• «диван и журнальный столик»\n"
        "• «весь старый шкаф около окна»\n"
        "• «стулья и стол, а пол почистить»"
    )
    await state.set_state(GenStates.waiting_to_remove)


@router.message(GenStates.waiting_to_remove, F.text)
async def receive_to_remove(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    raw = message.text.strip()
    if not raw or len(raw) > 300:
        await message.answer("Опиши коротко (до 300 символов).")
        return
    await state.update_data(to_remove=raw)
    await message.answer(f"✓ Убираем: {raw}")
    await _ask_to_add(message, state)


async def _ask_to_add(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✨ Что ПОСТАВИТЬ и КУДА?\n\n"
        "Опиши свободно. Например:\n"
        "• «шкаф в угол около окна»\n"
        "• «диван у дальней стены»\n"
        "• «обеденный стол со стульями в центре»"
    )
    await state.set_state(GenStates.waiting_to_add)


@router.message(GenStates.waiting_to_add, F.text)
async def receive_to_add(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    raw = message.text.strip()
    if not raw or len(raw) > 300:
        await message.answer("Опиши коротко (до 300 символов).")
        return
    await state.update_data(to_add_with_placement=raw)
    await message.answer(f"✓ Поставим: {raw}")
    await _run_stage_a(message, state)


async def _run_stage_a(message: Message, state: FSMContext) -> None:
    """ЭТАП А: оценить размер свободного места + сгенерировать промежуточную картинку."""
    data = await state.get_data()
    scene_url = data["scene_url"]
    to_remove = data["to_remove"]
    to_add_with_placement = data["to_add_with_placement"]
    ceiling_cm = data.get("ceiling_cm") or 270
    room_description = data.get("room_description") or ""

    await message.answer(
        "⏳ Оцениваю размер свободного места и убираю с фото то что ты попросил...\n"
        "Это ~30 секунд."
    )

    slot = await estimate_post_removal_slot(
        scene_url=scene_url,
        to_remove=to_remove,
        to_add_with_placement=to_add_with_placement,
        ceiling_cm=ceiling_cm,
        room_description=room_description,
    )
    await state.update_data(estimated_slot=slot)

    image_result = await generate_removal_with_dimensions(
        scene_url=scene_url,
        to_remove=to_remove,
        to_add_with_placement=to_add_with_placement,
        ceiling_cm=ceiling_cm,
        room_description=room_description,
        slot_dims=slot,
    )

    if not image_result["success"]:
        await message.answer(
            f"❌ Не получилось сделать промежуточную картинку: "
            f"{image_result.get('error', 'неизвестная ошибка')}\n\n"
            "Попробуй /start с другим фото."
        )
        await state.clear()
        return

    free_area = slot.get("free_area_after_removal") or {}
    w = free_area.get("width_cm", "?")
    d = free_area.get("depth_cm", "?")
    h = free_area.get("height_cm", "?")
    confidence = slot.get("confidence", "?")
    reasoning = slot.get("reasoning") or ""

    caption_lines = [
        "Вот как будет выглядеть комната без того что попросил убрать.",
        "На фото нарисованы линии и подписи с размерами.",
        "",
        "Размеры свободного места:",
        f"• Ширина: {w} см",
        f"• Глубина: {d} см",
        f"• Высота: {h} см",
        f"(точность оценки: {confidence})",
    ]
    if reasoning:
        caption_lines.append("")
        caption_lines.append(f"💭 {reasoning}")

    photo = BufferedInputFile(image_result["image_bytes"], filename="stage_a.png")
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Размеры правильные", callback_data="slot:confirm")
    kb.button(text="✏️ Поправлю", callback_data="slot:edit")
    kb.adjust(2)

    await message.answer_photo(photo, caption="\n".join(caption_lines), reply_markup=kb.as_markup())
    await state.set_state(GenStates.confirming_slot_dimensions)


@router.callback_query(F.data == "slot:confirm", GenStates.confirming_slot_dimensions)
async def slot_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Принято. Теперь загрузи фото товара (как в каталоге — на белом фоне)."
        )
    await state.set_state(GenStates.waiting_product_photo)


@router.callback_query(F.data == "slot:edit", GenStates.confirming_slot_dimensions)
async def slot_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Напиши правильные размеры свободного места в сантиметрах.\n"
            "Пример: «ширина 230, глубина 80, высота 240»\n"
            "Или коротко: «230 на 80 на 240»"
        )
    await state.set_state(GenStates.editing_slot_dimensions)


_DIM_LABEL_RE = re.compile(
    r"(ширина|шир|глубина|глуб|высота|выс)\s*[:=\s]?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_DIM_TRIPLE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:на|x|х|×|\*)\s*(\d+(?:[.,]\d+)?)\s*(?:на|x|х|×|\*)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def _parse_slot_edit(text: str, current: dict) -> dict | None:
    """Парсит правки размеров. Возвращает новый dict free_area_after_removal или None."""
    cur_w = int(current.get("width_cm", 0)) if current else 0
    cur_d = int(current.get("depth_cm", 0)) if current else 0
    cur_h = int(current.get("height_cm", 0)) if current else 0

    # Сначала пробуем формат «230 на 80 на 240»
    triple = _DIM_TRIPLE_RE.search(text)
    if triple:
        w, d, h = (int(round(float(v.replace(",", ".")))) for v in triple.groups())
        return {"width_cm": w, "depth_cm": d, "height_cm": h}

    # Формат с метками
    found: dict[str, int] = {}
    for label, num in _DIM_LABEL_RE.findall(text):
        value = int(round(float(num.replace(",", "."))))
        label_low = label.lower()
        if label_low.startswith("шир"):
            found["width_cm"] = value
        elif label_low.startswith("глуб"):
            found["depth_cm"] = value
        elif label_low.startswith("выс"):
            found["height_cm"] = value
    if not found:
        return None

    return {
        "width_cm": found.get("width_cm", cur_w),
        "depth_cm": found.get("depth_cm", cur_d),
        "height_cm": found.get("height_cm", cur_h),
    }


@router.message(GenStates.editing_slot_dimensions, F.text)
async def receive_slot_edit(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    data = await state.get_data()
    estimated_slot = data.get("estimated_slot") or {}
    current = estimated_slot.get("free_area_after_removal") or {}

    new_dims = _parse_slot_edit(message.text, current)
    if not new_dims:
        await message.answer(
            "Не понял размеры. Напиши с метками («ширина 230, высота 240») или «230 на 80 на 240»."
        )
        return

    # Sanity check
    for axis, val in new_dims.items():
        if not (10 <= val <= 600):
            await message.answer(f"{axis} = {val} — не похоже на правду. Жду размеры в см между 10 и 600.")
            return

    # Сохраняем как final_slot
    final_slot = {
        "free_area_after_removal": new_dims,
        "confidence": "user_specified",
        "reasoning": "размеры указаны пользователем",
    }
    await state.update_data(estimated_slot=final_slot)

    await message.answer(
        f"✓ Записал размеры:\n"
        f"• Ширина: {new_dims['width_cm']} см\n"
        f"• Глубина: {new_dims['depth_cm']} см\n"
        f"• Высота: {new_dims['height_cm']} см\n\n"
        "Теперь загрузи фото товара (как в каталоге — на белом фоне)."
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
        "Размеры товара в сантиметрах?\n\n"
        "Формат: «длина x ширина x высота».\n"
        "Например для дивана: 220x90x85.\n"
        "Для обеденного стола: 140x90x76.\n\n"
        "Если не знаешь — напиши «не знаю»."
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
            "Не понял формат. Напиши три числа через «x», например «220x90x85». Или «не знаю»."
        )
        return
    await state.update_data(product_dims=product_dims)

    if product_dims is None:
        # Размеры неизвестны — пропускаем pre-flight, идём сразу в финал (заглушка генерации)
        await message.answer(
            "✓ Размеры не указаны — пропускаю предварительную проверку.\n"
            "Запускаю подбор..."
        )
        await _finish(message, state, slot=None, size_check=None)
        return

    await _run_pre_flight_check(message, state)


async def _run_pre_flight_check(message: Message, state: FSMContext) -> None:
    """Сравниваем размеры товара с подтверждённым слотом (estimated_slot)."""
    data = await state.get_data()
    estimated_slot = data.get("estimated_slot") or {}
    free_area = estimated_slot.get("free_area_after_removal") or {}
    product_dims = data["product_dims"]

    # Формат который ждёт compare_product_to_slot: {"estimated_slot": {...}, "confidence": ...}
    slot_for_compare = {
        "estimated_slot": {
            "width_cm": free_area.get("width_cm", 200),
            "depth_cm": free_area.get("depth_cm", 90),
            "height_cm": free_area.get("height_cm", 220),
        },
        "confidence": estimated_slot.get("confidence", "medium"),
    }

    try:
        size_check = compare_product_to_slot(product_dims, slot_for_compare)
    except ValueError:
        logger.exception("Не удалось сравнить размеры")
        await message.answer("❌ Не удалось проверить размеры. Запускаю генерацию как есть.")
        await _finish(message, state, size_check=None)
        return

    await state.update_data(size_check=size_check)

    verdict = size_check["verdict"]
    if verdict == "fits_ok":
        await _finish(message, state, size_check=size_check)
        return

    # Marginal или doesnt_fit — кнопки
    overrun = size_check["max_overrun_pct"]
    slot_dims = size_check["slot_dims_cm"]
    p_len, p_width, p_height = product_dims

    if verdict == "marginal":
        text = (
            f"⚠️ Товар `{int(p_len)}x{int(p_width)}x{int(p_height)}` "
            f"примерно на {overrun:.0f}% больше свободного места "
            f"({slot_dims['width']}x{slot_dims['depth']}x{slot_dims['height']} см).\n\n"
            "Скорее всего будет тесновато. Что делаем?"
        )
    else:  # doesnt_fit
        text = (
            f"❌ Товар `{int(p_len)}x{int(p_width)}x{int(p_height)}` "
            f"на {overrun:.0f}% больше свободного места "
            f"({slot_dims['width']}x{slot_dims['depth']}x{slot_dims['height']} см).\n\n"
            "Возьми меньший размер или другой товар."
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Всё равно попробовать", callback_data="size:proceed")
    kb.button(text="🔄 Проверить размеры", callback_data="size:retry")
    kb.adjust(2)

    await message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(GenStates.confirming_size_mismatch)


@router.callback_query(F.data == "size:proceed", GenStates.confirming_size_mismatch)
async def size_proceed(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await _finish(callback.message, state, size_check=data.get("size_check"))


@router.callback_query(F.data == "size:retry", GenStates.confirming_size_mismatch)
async def size_retry(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Хорошо. Перепроверь размеры товара на сайте магазина и пришли /start заново."
        )
    await state.clear()


# --- Финал: этап Б (реальная генерация с товаром) ---


async def _finish(
    message: Message,
    state: FSMContext,
    size_check: dict | None,
) -> None:
    data = await state.get_data()
    user_id = message.from_user.id if message.from_user else 0

    # 1. Лимит 5 успешных генераций в сутки
    recent = count_recent_generations(user_id, hours=24)
    if recent >= DAILY_GENERATION_LIMIT:
        await message.answer(
            f"⚠️ Дневной лимит {DAILY_GENERATION_LIMIT} генераций исчерпан. "
            "Возвращайся завтра — лимит обнулится."
        )
        await state.clear()
        return

    estimated_slot = data.get("estimated_slot") or {}

    # 2. Сохраняем сессию ДО генерации
    session_id = log_session(
        tg_user_id=user_id,
        scene_url=data.get("scene_url"),
        product_url=data.get("product_url"),
        target_class=None,
        to_remove=data.get("to_remove"),
        to_add=data.get("to_add_with_placement"),
        room_dims_m=None,
        product_dims_cm=data.get("product_dims"),
        scene_quality=data.get("scene_qc"),
        product_quality=data.get("product_qc"),
        ceiling_height_cm=data.get("ceiling_cm"),
        room_description=data.get("room_description"),
        slot_estimation=estimated_slot,
        size_check=size_check,
    )

    await message.answer(
        "🎨 Готовлю финальное фото с твоим товаром...\n"
        "Это ~30 секунд."
    )

    # 3. Этап Б: финальная генерация
    product_dims = data.get("product_dims") or (100, 100, 100)
    result = await generate_room_with_product(
        scene_url=data["scene_url"],
        product_url=data["product_url"],
        to_remove=data.get("to_remove") or "",
        to_add_with_placement=data.get("to_add_with_placement") or "",
        ceiling_cm=data.get("ceiling_cm") or 270,
        room_description=data.get("room_description") or "",
        final_slot_dims=estimated_slot,
        product_dims_cm=product_dims,
    )

    # 4. Лог генерации
    log_generation(
        session_id=session_id,
        success=result["success"],
        error_type=result.get("error_type"),
        result_url=None,
        cost_usd=result.get("cost_estimate_usd"),
        duration_sec=result.get("duration_sec"),
        generation_meta={
            "model": result.get("model"),
            "quality": result.get("quality"),
            "size": result.get("size"),
            "error": result.get("error"),
            "stage": "final",
        },
    )

    # 5. Отправляем результат
    if not result["success"]:
        await message.answer(
            f"❌ Не получилось сгенерировать: {result.get('error', 'неизвестная ошибка')}\n\n"
            "Попробуй /start с другими фото."
        )
        await state.clear()
        return

    image_bytes = result["image_bytes"]
    photo = BufferedInputFile(image_bytes, filename="result.png")

    caption_lines = [
        f"✨ Готово! Сессия #{session_id}",
        f"Заняло {result['duration_sec']}с",
    ]
    if size_check and size_check.get("verdict") != "fits_ok":
        caption_lines.append(f"⚠️ Размер был на грани ({size_check.get('max_overrun_pct', 0):.0f}% больше места)")
    caption_lines.append("\nКоманда /start — попробовать ещё раз.")

    await message.answer_photo(photo, caption="\n".join(caption_lines))
    await state.clear()


# --- Неподходящий контент в неправильном state ---


@router.message(GenStates.waiting_scene)
async def waiting_scene_other(message: Message) -> None:
    await message.answer("Сейчас жду фото комнаты, а не текст. Загрузи фото.")


@router.message(GenStates.waiting_product_photo)
async def waiting_product_other(message: Message) -> None:
    await message.answer("Сейчас жду фото товара. Загрузи фото.")
