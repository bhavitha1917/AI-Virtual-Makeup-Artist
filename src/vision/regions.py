"""Landmark-anchored image regions (face mask, skin sampling discs, exclusion masks)."""

from __future__ import annotations

import cv2
import numpy as np

from src.config import SETTINGS, SkinThresholds
from src.vision import landmark_indices as idx
from src.vision.face_landmarks import FaceLandmarks

REGION_NAMES = ("right_cheek", "left_cheek", "forehead")


def hull_mask(shape: tuple[int, int], points: np.ndarray) -> np.ndarray:
    """Filled convex hull of ``points`` as a boolean mask of ``shape`` (h, w)."""
    mask = np.zeros(shape, dtype=np.uint8)
    pts = np.round(points).astype(np.int32)
    if len(pts) >= 3:
        cv2.fillConvexPoly(mask, cv2.convexHull(pts), 1)
    return mask.astype(bool)


def disc_mask(shape: tuple[int, int], center: np.ndarray, radius: float) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if radius >= 1:
        cv2.circle(mask, (int(round(center[0])), int(round(center[1]))), int(round(radius)), 1, -1)
    return mask.astype(bool)


def face_mask(shape: tuple[int, int], lm: FaceLandmarks) -> np.ndarray:
    return hull_mask(shape, lm.points[list(idx.FACE_OVAL)])


def exclusion_mask(shape: tuple[int, int], lm: FaceLandmarks,
                   cfg: SkinThresholds = SETTINGS.skin) -> np.ndarray:
    """Eyes, eyebrows and lips (convex hulls), dilated proportionally to face size."""
    mask = np.zeros(shape, dtype=bool)
    for contour in idx.EXCLUSION_CONTOURS:
        mask |= hull_mask(shape, lm.points[list(contour)])
    k = max(1, int(round(cfg.exclusion_dilate_iod * lm.inter_ocular_distance)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)


def sampling_discs(lm: FaceLandmarks, cfg: SkinThresholds = SETTINGS.skin
                   ) -> dict[str, tuple[np.ndarray, float]]:
    """Centre and radius (px) of each skin sampling disc."""
    iod = lm.inter_ocular_distance
    return {
        "right_cheek": (lm[idx.RIGHT_CHEEK_CENTER], cfg.cheek_radius_iod * iod),
        "left_cheek": (lm[idx.LEFT_CHEEK_CENTER], cfg.cheek_radius_iod * iod),
        "forehead": (lm[idx.FOREHEAD_CENTER], cfg.forehead_radius_iod * iod),
    }


def skin_region_masks(shape: tuple[int, int], lm: FaceLandmarks,
                      cfg: SkinThresholds = SETTINGS.skin) -> dict[str, np.ndarray]:
    """Sampling discs ∩ face mask − exclusions, per region."""
    face = face_mask(shape, lm)
    excluded = exclusion_mask(shape, lm, cfg)
    return {
        name: disc_mask(shape, center, radius) & face & ~excluded
        for name, (center, radius) in sampling_discs(lm, cfg).items()
    }


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB uint8 array (..., 3) → CIELAB float32 (L* in [0, 100]) via OpenCV (D65)."""
    arr = np.asarray(rgb, dtype=np.float32) / 255.0
    flat = arr.reshape(-1, 1, 3)
    lab = cv2.cvtColor(flat, cv2.COLOR_RGB2LAB)
    return lab.reshape(arr.shape)
