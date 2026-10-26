"""Eye shape and tilt estimation from multiple normalized measurements (methodology §6)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from src.config import SETTINGS, GeometryThresholds
from src.core.enums import EyeShape, EyeTilt
from src.core.features import EYE_SHAPE, EYE_TILT, FeatureEstimate, FeatureStatus
from src.vision import landmark_indices as idx
from src.vision.face_landmarks import FaceLandmarks


@dataclass(frozen=True)
class EyeMeasurements:
    width: float
    openings: tuple[float, float, float]
    taper: float
    tilt_deg: float
    lid_space: float

    @property
    def mean_opening(self) -> float:
        return float(np.mean(self.openings))


def rotate_points(points: np.ndarray, degrees: float, center: np.ndarray) -> np.ndarray:
    """Rotate points by ``degrees`` (image coordinates) about ``center``."""
    t = math.radians(degrees)
    rot = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    return (points - center) @ rot.T + center


def measure_eye(points: np.ndarray, eye: Mapping) -> EyeMeasurements | None:
    """Measure one eye from roll-corrected points; ``None`` if the width is degenerate."""
    outer, inner = points[eye["outer"]], points[eye["inner"]]
    width = float(np.linalg.norm(outer - inner))
    if width < 1e-6:
        return None
    openings = tuple(float(np.linalg.norm(points[u] - points[lo])) / width
                     for u, lo in zip(eye["upper"], eye["lower"], strict=True))
    centre = openings[1]
    taper = float("inf") if centre < 1e-9 else (openings[0] + openings[2]) / (2 * centre)
    tilt = math.degrees(math.atan2(inner[1] - outer[1], abs(outer[0] - inner[0])))
    lid_space = float(np.linalg.norm(points[eye["upper"][1]] - points[eye["brow"]])) / width
    return EyeMeasurements(width, openings, taper, tilt, lid_space)  # type: ignore[arg-type]


def classify_single_eye(m: EyeMeasurements, cfg: GeometryThresholds = SETTINGS.geometry
                        ) -> str | None:
    """Return 'closed', a shape value, or ``None`` when the measurements are ambiguous."""
    o = m.mean_opening
    if o < cfg.eye_closed_opening:
        return "closed"
    if m.lid_space <= cfg.hooded_max_lid_space and o < cfg.hooded_max_opening:
        return EyeShape.HOODED.value
    if o >= cfg.round_min_opening and m.taper >= cfg.round_min_taper:
        return EyeShape.ROUND.value
    if (cfg.almond_min_opening <= o < cfg.almond_max_opening and m.taper <= cfg.almond_max_taper
            and m.lid_space > cfg.almond_min_lid_space):
        return EyeShape.ALMOND.value
    return None


def classify_eye_shape(right: EyeMeasurements, left: EyeMeasurements,
                       cfg: GeometryThresholds = SETTINGS.geometry) -> FeatureEstimate:
    labels = (classify_single_eye(right, cfg), classify_single_eye(left, cfg))
    meas = {"opening_right": round(right.mean_opening, 3),
            "opening_left": round(left.mean_opening, 3),
            "taper_right": round(right.taper, 3), "taper_left": round(left.taper, 3),
            "lid_space_right": round(right.lid_space, 3),
            "lid_space_left": round(left.lid_space, 3)}
    if "closed" in labels:
        return FeatureEstimate.unknown(EYE_SHAPE, "The eyes appear closed in this photo.")
    if labels[0] is not None and labels[0] == labels[1]:
        return FeatureEstimate(EYE_SHAPE, FeatureStatus.ESTIMATED, value=labels[0],
                               reasons=("Hooded-eye detection is approximate; the landmark "
                                        "model does not capture eyelid creases.",),
                               measurements=meas)
    found = tuple(lab for lab in labels if lab is not None)
    reason = ("The two eyes measured differently." if len(set(found)) > 1 or len(found) == 1
              else "The measurements do not clearly match one eye-shape category.")
    return FeatureEstimate(EYE_SHAPE, FeatureStatus.UNCERTAIN, candidates=found,
                           reasons=(reason,), measurements=meas)


def classify_eye_tilt(right: EyeMeasurements, left: EyeMeasurements,
                      cfg: GeometryThresholds = SETTINGS.geometry) -> FeatureEstimate:
    mean_tilt = (right.tilt_deg + left.tilt_deg) / 2
    meas = {"tilt_right_deg": round(right.tilt_deg, 2), "tilt_left_deg": round(left.tilt_deg, 2),
            "tilt_mean_deg": round(mean_tilt, 2)}
    if abs(right.tilt_deg - left.tilt_deg) > cfg.tilt_max_eye_disagreement_deg:
        return FeatureEstimate(EYE_TILT, FeatureStatus.UNCERTAIN,
                               reasons=("The two eyes show different tilts.",), measurements=meas)
    if mean_tilt > cfg.tilt_up_deg:
        value = EyeTilt.UPTURNED.value
    elif mean_tilt < cfg.tilt_down_deg:
        value = EyeTilt.DOWNTURNED.value
    elif abs(mean_tilt) <= cfg.tilt_neutral_abs_deg:
        value = EyeTilt.NEUTRAL.value
    else:
        other = EyeTilt.UPTURNED.value if mean_tilt > 0 else EyeTilt.DOWNTURNED.value
        return FeatureEstimate(EYE_TILT, FeatureStatus.UNCERTAIN,
                               candidates=(EyeTilt.NEUTRAL.value, other),
                               reasons=("The tilt is between neutral and "
                                        f"{other}.",), measurements=meas)
    return FeatureEstimate(EYE_TILT, FeatureStatus.ESTIMATED, value=value, measurements=meas)


def estimate_eyes(lm: FaceLandmarks, reliable: bool, unreliable_reasons: tuple[str, ...] = ()
                  ) -> tuple[FeatureEstimate, FeatureEstimate]:
    if not reliable:
        reasons = unreliable_reasons or ("Eye measurements are unreliable in this photo.",)
        return (FeatureEstimate.unknown(EYE_SHAPE, *reasons),
                FeatureEstimate.unknown(EYE_TILT, *reasons))
    center = (lm.eye_center(idx.RIGHT_EYE) + lm.eye_center(idx.LEFT_EYE)) / 2
    points = rotate_points(lm.points, -lm.roll_degrees, center)
    right, left = measure_eye(points, idx.RIGHT_EYE), measure_eye(points, idx.LEFT_EYE)
    if right is None or left is None:
        reason = "Eye corners could not be measured."
        return (FeatureEstimate.unknown(EYE_SHAPE, reason),
                FeatureEstimate.unknown(EYE_TILT, reason))
    return classify_eye_shape(right, left), classify_eye_tilt(right, left)
