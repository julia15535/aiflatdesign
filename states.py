"""FSM-состояния диалога бота.

Подробнее: .memory_bank/domain/states.md
"""

from aiogram.fsm.state import State, StatesGroup


class GenStates(StatesGroup):
    # Онбординг (туториал) — пока не реализован, добавится в Шаге 6
    onboarding_step_1 = State()
    onboarding_step_2 = State()
    onboarding_step_3 = State()
    onboarding_step_4 = State()

    # Основной flow
    waiting_scene = State()
    waiting_room_dims = State()
    waiting_target_class = State()
    waiting_product_photo = State()
    waiting_product_dims = State()
    confirming_warning = State()  # для будущего size_mismatch (Шаг 3)
