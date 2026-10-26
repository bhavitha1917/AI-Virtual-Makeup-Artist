"""Image-quality checks that decide which features can be estimated reliably."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.config import SETTINGS, QualityThresholds
from src.core.features import QualityCheck, Severity
from src.vision import landmark_indices as idx
from src.vision.face_landmarks import FaceLandmarks
from src.vision.regions import disc_mask, face_mask, rgb_to_lab, sampling_discs

SKIN_CHECKS = ("face_size", "sharpness", "exposure", "highlights", "shadows", "lighting_balance")
GEOMETRY_CHECKS = ("face_size", "head_yaw", "head_roll")


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[QualityCheck, ...]

    def _severity(self, check_id: str) -> Severity:
        for c in self.checks:
            if c.check_id == check_id:
                return c.severity
        return Severity.OK

    def any_fail(self, ids: tuple[str, ...]) -> bool:
        return any(self._severity(i) is Severity.FAIL for i in ids)

    def any_warning(self, ids: tuple[str, ...]) -> bool:
        return any(self._severity(i) is Severity.WARNING for i in ids)

    @property
    def skin_reliable(self) -> bool:
        return not self.any_fail(SKIN_CHECKS)

    @property
    def skin_warnings(self) -> bool:
        return self.any_warning(SKIN_CHECKS)

    @property
    def geometry_reliable(self) -> bool:
        return not self.any_fail(GEOMETRY_CHECKS)

    @property
    def eyes_reliable(self) -> bool:
        return (self.geometry_reliable and self._severity("eyes_open") is Severity.OK
                and self._severity("sharpness") is not Severity.FAIL)

    def messages(self, ids: tuple[str, ...], severity: Severity) -> tuple[str, ...]:
        return tuple(c.message for c in self.checks if c.check_id in ids and c.severity is severity)


def _grade(value: float, warn: float, fail: float, higher_is_worse: bool) -> Severity:
    if higher_is_worse:
        return Severity.FAIL if value > fail else Severity.WARNING if value > warn else Severity.OK
    return Severity.FAIL if value < fail else Severity.WARNING if value < warn else Severity.OK


def sharpness_score(rgb: np.ndarray, lm: FaceLandmarks, crop_width: int) -> float:
    """Variance of the Laplacian on the face bounding box resized to ``crop_width``."""
    h, w = rgb.shape[:2]
    pts = lm.points[list(idx.FACE_OVAL)]
    x0, y0 = np.clip(np.floor(pts.min(axis=0)).astype(int), 0, [w - 1, h - 1])
    x1, y1 = np.clip(np.ceil(pts.max(axis=0)).astype(int), 1, [w, h])
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    gray = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    scale = crop_width / gray.shape[1]
    gray = cv2.resize(gray, (crop_width, max(8, int(round(gray.shape[0] * scale)))),
                      interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def assess_quality(rgb: np.ndarray, lm: FaceLandmarks,
                   cfg: QualityThresholds = SETTINGS.quality) -> QualityReport:
    shape = rgb.shape[:2]
    checks: list[QualityCheck] = []

    face_width = lm.dist(idx.RIGHT_FACE_EDGE, idx.LEFT_FACE_EDGE)
    sev = _grade(face_width, cfg.face_width_warn_px, cfg.face_width_fail_px, False)
    checks.append(QualityCheck("face_size", sev, {
        Severity.OK: "Face size is sufficient.",
        Severity.WARNING: "The face is quite small in the frame; move closer for better detail.",
        Severity.FAIL: "The face is too small in the frame to analyse. Move closer to the camera.",
    }[sev], round(face_width, 1)))

    sharp = sharpness_score(rgb, lm, cfg.sharpness_crop_width)
    sev = _grade(sharp, cfg.sharpness_warn, cfg.sharpness_fail, False)
    checks.append(QualityCheck("sharpness", sev, {
        Severity.OK: "The photo is sharp enough.",
        Severity.WARNING: "The photo looks slightly soft; hold the camera steady.",
        Severity.FAIL: "The photo is too blurry. Hold the camera steady and make sure it focuses.",
    }[sev], round(sharp, 1)))

    fmask = face_mask(shape, lm)
    face_px = rgb[fmask]
    if face_px.size == 0:
        face_px = rgb.reshape(-1, 3)
    lab = rgb_to_lab(face_px)
    median_l = float(np.median(lab[:, 0]))
    if median_l < cfg.exposure_fail_low or median_l > cfg.exposure_fail_high:
        sev = Severity.FAIL
    elif median_l < cfg.exposure_warn_low or median_l > cfg.exposure_warn_high:
        sev = Severity.WARNING
    else:
        sev = Severity.OK
    too_dark = median_l < (cfg.exposure_warn_low + cfg.exposure_warn_high) / 2
    checks.append(QualityCheck("exposure", sev, "Exposure looks balanced." if sev is Severity.OK
                               else ("The face looks too dark. Face a window or soft light."
                                     if too_dark else
                                     "The face looks overexposed. Avoid direct, harsh light."),
                               round(median_l, 1)))

    peak = face_px.max(axis=1)
    hi = float(np.mean(peak >= cfg.clip_high_value))
    sev = _grade(hi, cfg.clip_warn_fraction, cfg.clip_fail_fraction, True)
    checks.append(QualityCheck("highlights", sev, "No significant blown-out highlights."
                               if sev is Severity.OK else
                               "Parts of the face are blown out by strong light or flash.",
                               round(hi, 3)))
    lo = float(np.mean(peak <= cfg.clip_low_value))
    sev = _grade(lo, cfg.clip_warn_fraction, cfg.clip_fail_fraction, True)
    checks.append(QualityCheck("shadows", sev, "No significant crushed shadows."
                               if sev is Severity.OK else
                               "Parts of the face are in very deep shadow.", round(lo, 3)))

    discs = sampling_discs(lm)
    cheeks = []
    for name in ("right_cheek", "left_cheek"):
        center, radius = discs[name]
        px = rgb[disc_mask(shape, center, radius) & fmask]
        cheeks.append(float(np.median(rgb_to_lab(px)[:, 0])) if len(px) else float("nan"))
    if any(np.isnan(cheeks)):
        balance, sev = float("nan"), Severity.FAIL
    else:
        balance = abs(cheeks[0] - cheeks[1])
        sev = _grade(balance, cfg.balance_warn, cfg.balance_fail, True)
    checks.append(QualityCheck("lighting_balance", sev, "Lighting is even across the face."
                               if sev is Severity.OK else
                               "One side of the face is noticeably darker; face the light "
                               "source directly.",
                               None if np.isnan(balance) else round(balance, 1)))

    yaw = lm.yaw_asymmetry
    sev = _grade(yaw, cfg.yaw_warn, cfg.yaw_fail, True)
    checks.append(QualityCheck("head_yaw", sev, "The face is turned toward the camera."
                               if sev is Severity.OK else
                               "The head is turned to one side; look straight at the camera.",
                               round(yaw, 2) if np.isfinite(yaw) else None))

    roll = abs(lm.roll_degrees)
    sev = _grade(roll, cfg.roll_warn_deg, cfg.roll_fail_deg, True)
    checks.append(QualityCheck("head_roll", sev, "The head is upright." if sev is Severity.OK
                               else "The head is tilted; hold it upright.", round(roll, 1)))

    blink = max(lm.blendshapes.get("eyeBlinkLeft", 0.0), lm.blendshapes.get("eyeBlinkRight", 0.0))
    sev = Severity.WARNING if blink > cfg.blink_warn else Severity.OK
    checks.append(QualityCheck("eyes_open", sev, "Eyes are open." if sev is Severity.OK else
                               "The eyes appear closed or mid-blink; eye shape will not be "
                               "estimated.", round(blink, 2)))
    return QualityReport(tuple(checks))
