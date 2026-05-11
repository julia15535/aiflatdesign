"""Stage 2 (pre-flight): сравнение размеров товара с оценкой слота.

Чистая алгоритмика без ИИ. На входе — кортеж (длина, ширина, высота) товара
в сантиметрах и словарь slot от scene_analysis.estimate_slot_dimensions.

На выходе — вердикт fits_ok / marginal / doesnt_fit + детали для UI.

Подробнее: .memory_bank/ai/size_check.md
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

Verdict = Literal["fits_ok", "marginal", "doesnt_fit"]

# Пороги (в процентах превышения товаром размера слота по любой оси)
_THRESHOLD_OK = 10  # ≤10% — впишется
_THRESHOLD_MARGINAL = 25  # 10-25% — на грани
# >25% — точно не влезет

# Доп. толерантность когда уверенность ИИ низкая
_LOW_CONFIDENCE_BONUS = 10


def compare_product_to_slot(
    product_dims_cm: tuple[float, float, float],
    slot: dict,
) -> dict:
    """Сравнить продукт со слотом.

    Args:
        product_dims_cm: (длина, ширина/глубина, высота) в см.
            Соответствие осей: длина → width_cm, ширина → depth_cm, высота → height_cm.
        slot: словарь из scene_analysis с полями estimated_slot и confidence.

    Returns:
        dict с полями verdict, fits, max_overrun_pct, breakdown, slot_dims, product_dims.
    """
    estimated = slot.get("estimated_slot", {})
    slot_w = estimated.get("width_cm")
    slot_d = estimated.get("depth_cm")
    slot_h = estimated.get("height_cm")
    if not all(isinstance(v, (int, float)) and v > 0 for v in (slot_w, slot_d, slot_h)):
        raise ValueError(f"slot не содержит корректных размеров: {estimated!r}")

    p_len, p_width, p_height = product_dims_cm

    # Считаем "превышение" по каждой оси в процентах
    overrun_w = max(0.0, (p_len - slot_w) / slot_w) * 100
    overrun_d = max(0.0, (p_width - slot_d) / slot_d) * 100
    overrun_h = max(0.0, (p_height - slot_h) / slot_h) * 100

    max_overrun = max(overrun_w, overrun_d, overrun_h)

    # Корректировка порогов при low confidence
    confidence = slot.get("confidence", "medium")
    threshold_ok = _THRESHOLD_OK + (_LOW_CONFIDENCE_BONUS if confidence == "low" else 0)
    threshold_marginal = _THRESHOLD_MARGINAL + (_LOW_CONFIDENCE_BONUS if confidence == "low" else 0)

    if max_overrun <= threshold_ok:
        verdict: Verdict = "fits_ok"
        fits = True
    elif max_overrun <= threshold_marginal:
        verdict = "marginal"
        fits = False
    else:
        verdict = "doesnt_fit"
        fits = False

    breakdown = {
        "width": {"product": p_len, "slot": slot_w, "overrun_pct": round(overrun_w, 1)},
        "depth": {"product": p_width, "slot": slot_d, "overrun_pct": round(overrun_d, 1)},
        "height": {"product": p_height, "slot": slot_h, "overrun_pct": round(overrun_h, 1)},
    }

    logger.info(
        "Size check: product=%sx%sx%s vs slot=%sx%sx%s, overrun=%.1f%%, "
        "verdict=%s (confidence=%s, thr_ok=%d, thr_marg=%d)",
        p_len, p_width, p_height, slot_w, slot_d, slot_h, max_overrun,
        verdict, confidence, threshold_ok, threshold_marginal,
    )

    return {
        "verdict": verdict,
        "fits": fits,
        "max_overrun_pct": round(max_overrun, 1),
        "breakdown": breakdown,
        "slot_dims_cm": {"width": slot_w, "depth": slot_d, "height": slot_h},
        "product_dims_cm": {"width": p_len, "depth": p_width, "height": p_height},
        "confidence": confidence,
        "thresholds_used": {"ok": threshold_ok, "marginal": threshold_marginal},
    }
