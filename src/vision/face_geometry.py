"""Approximate face-shape estimation from normalized landmark ratios (methodology §5)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from src.config import SETTINGS, GeometryThresholds
from src.core.enums import FaceShape
from src.core.features import FACE_SHAPE, FeatureEstimate, FeatureStatus
from src.vision import landmark_indices as idx
from src.vision.face_landmarks import FaceLandmarks

Trap = tuple[float, float, float, float]


def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal membership: 0 outside [a, d], 1 on [b, c], linear in between."""
    if b <= x <= c:
        return 1.0
    if x <= a or x >= d:
        return 0.0
    if x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)


SHAPE_RULES: Mapping[FaceShape, Mapping[str, Trap]] = MappingProxyType({
    FaceShape.OVAL: {"length_ratio": (1.18, 1.25, 1.38, 1.45),
                     "jaw_ratio": (0.70, 0.74, 0.84, 0.88),
                     "chin_angle": (95, 100, 115, 120)},
    FaceShape.ROUND: {"length_ratio": (0.90, 0.95, 1.15, 1.22),
                      "jaw_ratio": (0.76, 0.80, 0.90, 0.94),
                      "chin_angle": (108, 115, 140, 150)},
    FaceShape.SQUARE: {"length_ratio": (0.90, 0.95, 1.20, 1.27),
                       "jaw_ratio": (0.84, 0.88, 1.05, 1.10),
                       "chin_angle": (105, 112, 140, 150)},
    FaceShape.HEART: {"forehead_minus_jaw": (0.06, 0.10, 0.40, 0.50),
                      "chin_angle": (80, 85, 102, 108),
                      "length_ratio": (1.10, 1.18, 1.42, 1.50)},
    FaceShape.OBLONG: {"length_ratio": (1.38, 1.45, 2.00, 2.10),
                       "jaw_ratio": (0.70, 0.75, 0.95, 1.00)},
})


@dataclass(frozen=True)
class FaceMeasurements:
    length_ratio: float
    forehead_ratio: float
    jaw_ratio: float
    chin_angle: float

    @property
    def forehead_minus_jaw(self) -> float:
        return self.forehead_ratio - self.jaw_ratio

    def as_dict(self) -> dict[str, float]:
        return {"length_ratio": round(self.length_ratio, 3),
                "forehead_ratio": round(self.forehead_ratio, 3),
                "jaw_ratio": round(self.jaw_ratio, 3),
                "chin_angle": round(self.chin_angle, 1)}


def angle_at(p_vertex: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float | None:
    v1, v2 = p1 - p_vertex, p2 - p_vertex
    n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
    if n1 < 1e-9 or n2 < 1e-9:
        return None
    cos = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(cos))


def compute_face_measurements(lm: FaceLandmarks,
                              cfg: GeometryThresholds = SETTINGS.geometry
                              ) -> FaceMeasurements | None:
    """Return normalized ratios, or ``None`` when the geometry is degenerate."""
    cheek = lm.dist(idx.RIGHT_FACE_EDGE, idx.LEFT_FACE_EDGE)
    if not math.isfinite(cheek) or cheek < cfg.min_cheek_width_px:
        return None
    chin = angle_at(lm[idx.CHIN], lm[idx.RIGHT_JAW], lm[idx.LEFT_JAW])
    if chin is None:
        return None
    return FaceMeasurements(
        length_ratio=lm.dist(idx.FOREHEAD_TOP, idx.CHIN) / cheek,
        forehead_ratio=lm.dist(idx.RIGHT_FOREHEAD, idx.LEFT_FOREHEAD) / cheek,
        jaw_ratio=lm.dist(idx.RIGHT_JAW, idx.LEFT_JAW) / cheek,
        chin_angle=chin,
    )


def shape_scores(m: FaceMeasurements) -> dict[FaceShape, float]:
    values = {"length_ratio": m.length_ratio, "jaw_ratio": m.jaw_ratio,
              "chin_angle": m.chin_angle, "forehead_minus_jaw": m.forehead_minus_jaw}
    return {
        shape: sum(trapezoid(values[k], *t) for k, t in rules.items()) / len(rules)
        for shape, rules in SHAPE_RULES.items()
    }


def classify_face_shape(m: FaceMeasurements, cfg: GeometryThresholds = SETTINGS.geometry
                        ) -> FeatureEstimate:
    scores = shape_scores(m)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].value))
    (best, s1), (second, s2) = ranked[0], ranked[1]
    meas = m.as_dict()
    if s1 < cfg.face_min_best_score:
        return FeatureEstimate(FACE_SHAPE, FeatureStatus.UNCERTAIN,
                               candidates=(best.value, second.value),
                               reasons=("The measurements do not closely match any face-shape "
                                        "category.",), measurements=meas)
    if s1 - s2 < cfg.face_min_margin:
        return FeatureEstimate(FACE_SHAPE, FeatureStatus.UNCERTAIN,
                               candidates=(best.value, second.value),
                               reasons=("The measurements sit between two face-shape "
                                        "categories.",), measurements=meas)
    return FeatureEstimate(FACE_SHAPE, FeatureStatus.ESTIMATED, value=best.value,
                           measurements=meas)


def estimate_face_shape(lm: FaceLandmarks, reliable: bool, unreliable_reasons: tuple[str, ...] = ()
                        ) -> FeatureEstimate:
    if not reliable:
        return FeatureEstimate.unknown(FACE_SHAPE, *(unreliable_reasons or (
            "Head pose or face size prevents reliable face-shape measurement.",)))
    m = compute_face_measurements(lm)
    if m is None:
        return FeatureEstimate.unknown(FACE_SHAPE, "Face measurements were degenerate.")
    return classify_face_shape(m)
