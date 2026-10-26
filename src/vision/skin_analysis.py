"""Skin depth and possible-undertone estimation from landmark-anchored skin samples.

See docs/methodology.md §4. These are heuristic estimates from uncalibrated images; the
functions return ``unknown`` or ``uncertain`` rather than forcing a category.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans

from src.config import SETTINGS, SkinThresholds
from src.core.enums import DEPTH_ORDER, Undertone
from src.core.features import SKIN_DEPTH, UNDERTONE, FeatureEstimate, FeatureStatus, Severity
from src.vision.face_landmarks import FaceLandmarks
from src.vision.image_quality import SKIN_CHECKS, QualityReport
from src.vision.regions import face_mask, rgb_to_lab, skin_region_masks

UNDERTONE_ORDER = (Undertone.COOL, Undertone.NEUTRAL, Undertone.WARM)


@dataclass(frozen=True)
class SkinAnalysis:
    depth: FeatureEstimate
    undertone: FeatureEstimate
    measurements: Mapping[str, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    kept_regions: tuple[str, ...] = ()
    excluded_regions: Mapping[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- colour maths
def ita_degrees(l_star: float, b_star: float) -> float:
    """Individual Typology Angle: atan2(L* − 50, b*) in degrees."""
    return math.degrees(math.atan2(l_star - 50.0, b_star))


def hue_angle(a_star: float, b_star: float) -> float:
    """CIELAB hue angle h_ab in degrees, in (−180, 180]."""
    return math.degrees(math.atan2(b_star, a_star))


def delta_e76(lab1: np.ndarray, lab2: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(lab1, float) - np.asarray(lab2, float)))


def depth_band(ita: float, boundaries: tuple[float, ...]) -> int:
    """Index into DEPTH_ORDER for an ITA value (boundaries descending)."""
    for i, bound in enumerate(boundaries):
        if ita > bound:
            return i
    return len(boundaries)


# --------------------------------------------------------------------------- pixel handling
def filter_pixels(rgb_pixels: np.ndarray, cfg: SkinThresholds = SETTINGS.skin,
                  clip_high: int = SETTINGS.quality.clip_high_value,
                  clip_low: int = SETTINGS.quality.clip_low_value) -> np.ndarray:
    """Remove clipped pixels, convert to Lab, keep L* within the configured percentiles."""
    if len(rgb_pixels) == 0:
        return np.empty((0, 3), np.float32)
    peak = rgb_pixels.max(axis=1)
    px = rgb_pixels[(peak < clip_high) & (peak > clip_low)]
    if len(px) == 0:
        return np.empty((0, 3), np.float32)
    lab = rgb_to_lab(px)
    lo, hi = np.percentile(lab[:, 0], [cfg.trim_low_percentile, cfg.trim_high_percentile])
    return lab[(lab[:, 0] >= lo) & (lab[:, 0] <= hi)]


def screen_regions(region_lab: Mapping[str, np.ndarray], cfg: SkinThresholds = SETTINGS.skin
                   ) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Drop regions with too few pixels or whose median is a colour outlier (ΔE > threshold)."""
    kept: dict[str, np.ndarray] = {}
    excluded: dict[str, str] = {}
    for name, lab in region_lab.items():
        if len(lab) < cfg.min_region_pixels:
            excluded[name] = "insufficient skin pixels"
        else:
            kept[name] = lab
    if len(kept) >= 2:
        medians = {n: np.median(v, axis=0) for n, v in kept.items()}
        reference = np.median(np.stack(list(medians.values())), axis=0)
        for name, med in medians.items():
            if delta_e76(med, reference) > cfg.outlier_delta_e:
                excluded[name] = "colour differs strongly from other regions (possibly obstructed)"
        kept = {n: v for n, v in kept.items() if n not in excluded}
    return kept, excluded


def dominant_cluster_delta(lab_pixels: np.ndarray, cfg: SkinThresholds = SETTINGS.skin
                           ) -> tuple[float, float] | None:
    """K-Means diagnostic: (ΔE between largest-cluster centre and median, largest share)."""
    if len(lab_pixels) < max(30, cfg.kmeans_clusters * 10):
        return None
    rng = np.random.default_rng(cfg.kmeans_seed)
    sample = lab_pixels
    if len(sample) > cfg.kmeans_max_samples:
        sample = sample[rng.choice(len(sample), cfg.kmeans_max_samples, replace=False)]
    km = KMeans(n_clusters=cfg.kmeans_clusters, n_init=4, random_state=cfg.kmeans_seed)
    labels = km.fit_predict(sample)
    counts = np.bincount(labels, minlength=cfg.kmeans_clusters)
    top = int(np.argmax(counts))
    return (delta_e76(km.cluster_centers_[top], np.median(sample, axis=0)),
            float(counts[top] / counts.sum()))


def background_cast(rgb: np.ndarray, fmask: np.ndarray, cfg: SkinThresholds = SETTINGS.skin
                    ) -> tuple[bool | None, float, float]:
    """Gray-world cast check on pixels outside the face. ``None`` if too little background."""
    outside = ~fmask
    if outside.mean() < cfg.cast_min_background_fraction:
        return None, float("nan"), float("nan")
    px = rgb[outside]
    if len(px) > 50_000:
        px = px[:: len(px) // 50_000 + 1]
    lab = rgb_to_lab(px)
    mean_a, mean_b = float(lab[:, 1].mean()), float(lab[:, 2].mean())
    return (abs(mean_a) > cfg.cast_max_abs_a or abs(mean_b) > cfg.cast_max_abs_b), mean_a, mean_b


# --------------------------------------------------------------------------- classification
def classify_depth(ita: float, region_itas: list[float], b_star: float,
                   cfg: SkinThresholds = SETTINGS.skin) -> FeatureEstimate:
    meas = {"ita_degrees": round(ita, 2), "b_star": round(b_star, 2)}
    if b_star <= 0:
        return FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNKNOWN, reasons=(
            "Skin samples show no yellow component (b* ≤ 0), which suggests a strong colour cast;"
            " depth could not be estimated.",), measurements=meas)
    bounds = cfg.ita_boundaries
    band = depth_band(ita, bounds)
    spread = (max(region_itas) - min(region_itas)) if len(region_itas) > 1 else 0.0
    meas["ita_region_spread"] = round(spread, 2)
    if spread > cfg.ita_region_spread:
        bands = sorted({depth_band(v, bounds) for v in region_itas})
        cands = tuple(DEPTH_ORDER[i].value for i in range(bands[0], bands[-1] + 1))
        if len(cands) > 1:
            return FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN, candidates=cands,
                                   reasons=("Skin regions differ noticeably in brightness, "
                                            "usually because of uneven lighting.",),
                                   measurements=meas)
    near = [i for i, bound in enumerate(bounds) if abs(ita - bound) <= cfg.ita_margin]
    if near:
        i = near[0]  # boundary i separates DEPTH_ORDER[i] and DEPTH_ORDER[i + 1]
        return FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN,
                               candidates=(DEPTH_ORDER[i].value, DEPTH_ORDER[i + 1].value),
                               reasons=("The measurement is close to the boundary between two "
                                        "depth levels.",), measurements=meas)
    return FeatureEstimate(SKIN_DEPTH, FeatureStatus.ESTIMATED, value=DEPTH_ORDER[band].value,
                           measurements=meas)


def _undertone_band(h: float, cfg: SkinThresholds) -> int:
    if h < cfg.hue_cool_below:
        return 0
    if h > cfg.hue_warm_above:
        return 2
    return 1


def _nearest_neighbour_band(h: float, band: int, cfg: SkinThresholds) -> int:
    if band == 0:
        return 1
    if band == 2:
        return 1
    return 0 if abs(h - cfg.hue_cool_below) <= abs(h - cfg.hue_warm_above) else 2


def classify_undertone(h: float, region_hues: list[float], *, cast_suspected: bool | None,
                       quality_warnings: tuple[str, ...], cfg: SkinThresholds = SETTINGS.skin
                       ) -> FeatureEstimate:
    meas = {"hue_degrees": round(h, 2)}
    band = _undertone_band(h, cfg)
    reasons: list[str] = []
    spread = (max(region_hues) - min(region_hues)) if len(region_hues) > 1 else 0.0
    meas["hue_region_spread"] = round(spread, 2)
    if min(abs(h - cfg.hue_cool_below), abs(h - cfg.hue_warm_above)) <= cfg.hue_margin:
        reasons.append("The hue is close to the boundary between two undertone groups.")
    if spread > cfg.hue_region_spread:
        reasons.append("Skin regions disagree on hue.")
    if cast_suspected:
        reasons.append("The photo may have a colour cast (tinted lighting or white balance).")
    reasons.extend(quality_warnings)
    if reasons:
        other = _nearest_neighbour_band(h, band, cfg)
        cands = tuple(UNDERTONE_ORDER[i].value for i in sorted({band, other}))
        return FeatureEstimate(UNDERTONE, FeatureStatus.UNCERTAIN, candidates=cands,
                               reasons=tuple(reasons), measurements=meas)
    return FeatureEstimate(UNDERTONE, FeatureStatus.ESTIMATED, value=UNDERTONE_ORDER[band].value,
                           reasons=("Undertone from photos is easily affected by lighting; "
                                    "confirm it if you know yours.",), measurements=meas)


# --------------------------------------------------------------------------- pipeline
def analyze_skin(rgb: np.ndarray, lm: FaceLandmarks, quality: QualityReport,
                 cfg: SkinThresholds = SETTINGS.skin) -> SkinAnalysis:
    if not quality.skin_reliable:
        reasons = quality.messages(SKIN_CHECKS, Severity.FAIL)
        return SkinAnalysis(
            depth=FeatureEstimate.unknown(SKIN_DEPTH, *reasons),
            undertone=FeatureEstimate.unknown(UNDERTONE, *reasons),
        )
    shape = rgb.shape[:2]
    masks = skin_region_masks(shape, lm, cfg)
    region_lab = {name: filter_pixels(rgb[mask], cfg) for name, mask in masks.items()}
    kept, excluded = screen_regions(region_lab, cfg)
    if len(kept) < cfg.min_regions:
        reason = ("Not enough clear skin was visible (cheeks/forehead may be covered by hair, "
                  "glasses or shadow).")
        return SkinAnalysis(FeatureEstimate.unknown(SKIN_DEPTH, reason),
                            FeatureEstimate.unknown(UNDERTONE, reason),
                            excluded_regions=excluded)

    pooled = np.concatenate(list(kept.values()))
    l_star, a_star, b_star = (float(v) for v in np.median(pooled, axis=0))
    ita = ita_degrees(l_star, b_star)
    hue = hue_angle(a_star, b_star)
    medians = {n: np.median(v, axis=0) for n, v in kept.items()}
    region_itas = [ita_degrees(float(m[0]), float(m[2])) for m in medians.values()]
    region_hues = [hue_angle(float(m[1]), float(m[2])) for m in medians.values()]

    warnings: list[str] = []
    measurements: dict[str, float] = {"L_star": round(l_star, 2), "a_star": round(a_star, 2),
                                      "b_star": round(b_star, 2), "ita_degrees": round(ita, 2),
                                      "hue_degrees": round(hue, 2),
                                      "regions_used": float(len(kept))}
    diag = dominant_cluster_delta(pooled, cfg)
    if diag is not None:
        delta, share = diag
        measurements["kmeans_dominant_delta_e"] = round(delta, 2)
        measurements["kmeans_dominant_share"] = round(share, 3)
        if delta > cfg.kmeans_warn_delta_e:
            warnings.append("Skin samples are uneven (makeup, texture or lighting); estimates "
                            "may be less reliable.")
    cast, mean_a, mean_b = background_cast(rgb, face_mask(shape, lm), cfg)
    if cast is not None:
        measurements["background_mean_a"] = round(mean_a, 2)
        measurements["background_mean_b"] = round(mean_b, 2)
    if excluded:
        warnings.append("Some skin regions were ignored: " + "; ".join(
            f"{n.replace('_', ' ')} ({why})" for n, why in sorted(excluded.items())))

    depth = classify_depth(ita, region_itas, b_star, cfg)
    undertone = classify_undertone(
        hue, region_hues, cast_suspected=cast,
        quality_warnings=quality.messages(SKIN_CHECKS, Severity.WARNING), cfg=cfg)
    return SkinAnalysis(depth=depth, undertone=undertone, measurements=measurements,
                        warnings=tuple(warnings), kept_regions=tuple(sorted(kept)),
                        excluded_regions=excluded)
