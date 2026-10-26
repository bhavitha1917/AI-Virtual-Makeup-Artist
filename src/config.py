"""Centralized configuration: paths, limits and heuristic thresholds.

All thresholds are provisional engineering heuristics documented in
``docs/methodology.md``; they have not been validated on a labelled dataset.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
MODELS_DIR: Path = PROJECT_ROOT / "models"

APP_NAME = "The Beauty Studio"
APP_VERSION = "1.0.0"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ModelSettings:
    """MediaPipe Face Landmarker asset settings."""

    path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BEAUTY_STUDIO_MODEL_PATH", MODELS_DIR / "face_landmarker.task")
        )
    )
    url: str = (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    )
    sha256: str = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
    size_bytes: int = 3_758_596
    allow_download: bool = field(
        default_factory=lambda: _env_flag("BEAUTY_STUDIO_ALLOW_MODEL_DOWNLOAD", True)
    )
    download_timeout_s: float = 30.0
    max_faces: int = 2  # two, so that multi-face images can be rejected


@dataclass(frozen=True)
class ImageLimits:
    max_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 40_000_000
    min_side: int = 256
    processing_long_side: int = 1280
    overlay_long_side: int = 480
    allowed_formats: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})


@dataclass(frozen=True)
class QualityThresholds:
    face_width_warn_px: float = 180.0
    face_width_fail_px: float = 120.0
    sharpness_warn: float = 50.0
    sharpness_fail: float = 20.0
    sharpness_crop_width: int = 256
    exposure_warn_low: float = 35.0
    exposure_warn_high: float = 82.0
    exposure_fail_low: float = 25.0
    exposure_fail_high: float = 90.0
    clip_high_value: int = 250
    clip_low_value: int = 10
    clip_warn_fraction: float = 0.05
    clip_fail_fraction: float = 0.15
    balance_warn: float = 10.0
    balance_fail: float = 18.0
    yaw_warn: float = 1.30
    yaw_fail: float = 1.60
    roll_warn_deg: float = 20.0
    roll_fail_deg: float = 40.0
    blink_warn: float = 0.5


@dataclass(frozen=True)
class SkinThresholds:
    cheek_radius_iod: float = 0.20
    forehead_radius_iod: float = 0.18
    exclusion_dilate_iod: float = 0.05
    trim_low_percentile: float = 10.0
    trim_high_percentile: float = 90.0
    min_region_pixels: int = 150
    min_regions: int = 2
    outlier_delta_e: float = 15.0
    kmeans_clusters: int = 3
    kmeans_max_samples: int = 3000
    kmeans_seed: int = 0
    kmeans_warn_delta_e: float = 8.0
    # ITA lower bounds (degrees) for each depth, from lightest to deepest.
    # fair > 55, light 41–55, medium 28–41, tan 10–28, deep -30–10, rich < -30.
    ita_boundaries: tuple[float, ...] = (55.0, 41.0, 28.0, 10.0, -30.0)
    ita_margin: float = 3.0
    ita_region_spread: float = 15.0
    hue_cool_below: float = 52.0
    hue_warm_above: float = 60.0
    hue_margin: float = 2.0
    hue_region_spread: float = 8.0
    cast_min_background_fraction: float = 0.10
    cast_max_abs_a: float = 10.0
    cast_max_abs_b: float = 15.0


@dataclass(frozen=True)
class GeometryThresholds:
    min_cheek_width_px: float = 1.0
    min_iod_px: float = 10.0
    landmark_bounds_margin: float = 0.05
    face_min_best_score: float = 0.5
    face_min_margin: float = 0.15
    eye_closed_opening: float = 0.10
    hooded_max_lid_space: float = 0.33
    hooded_max_opening: float = 0.27
    round_min_opening: float = 0.33
    round_min_taper: float = 0.85
    almond_min_opening: float = 0.16
    almond_max_opening: float = 0.31
    almond_max_taper: float = 0.93
    almond_min_lid_space: float = 0.36
    tilt_up_deg: float = 4.0
    tilt_down_deg: float = -4.0
    tilt_neutral_abs_deg: float = 2.5
    tilt_max_eye_disagreement_deg: float = 5.0


@dataclass(frozen=True)
class RecommendationSettings:
    default_limit: int = 6
    strong_fit: float = 0.75
    good_fit: float = 0.55


@dataclass(frozen=True)
class Settings:
    model: ModelSettings = field(default_factory=ModelSettings)
    image: ImageLimits = field(default_factory=ImageLimits)
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    skin: SkinThresholds = field(default_factory=SkinThresholds)
    geometry: GeometryThresholds = field(default_factory=GeometryThresholds)
    recommendation: RecommendationSettings = field(default_factory=RecommendationSettings)
    log_level: str = field(
        default_factory=lambda: os.environ.get("BEAUTY_STUDIO_LOG_LEVEL", "INFO").upper()
    )


def get_settings() -> Settings:
    """Return settings resolved from defaults and environment variables."""
    return Settings()


SETTINGS: Settings = get_settings()
