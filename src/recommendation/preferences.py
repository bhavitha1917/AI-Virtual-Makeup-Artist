"""User preferences that steer recommendations. ``None`` means "no preference"."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.enums import (
    ColorFamily,
    ConcealerPurpose,
    CorrectionTarget,
    Coverage,
    Finish,
    Formulation,
    Intensity,
    Look,
)


@dataclass(frozen=True)
class RecommendationPreferences:
    look: Look | None = None
    finish: Finish | None = None
    coverage: Coverage | None = None
    concealer_purpose: ConcealerPurpose = ConcealerPurpose.BRIGHTENING
    correction_target: CorrectionTarget | None = None
    color_family: ColorFamily | None = None
    intensity: Intensity | None = None
    formulation: Formulation | None = None  # blush formulation or eyeliner type
