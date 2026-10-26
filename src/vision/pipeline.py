"""Single entry point for face analysis: bytes in, ``AnalysisResult`` out."""

from __future__ import annotations

import io
import logging
import time

import cv2
import numpy as np
from PIL import Image

from src.config import SETTINGS
from src.core.errors import FaceDetectionError
from src.core.features import (
    EYE_SHAPE,
    EYE_TILT,
    FACE_SHAPE,
    SKIN_DEPTH,
    UNDERTONE,
    AnalysisResult,
    Severity,
)
from src.vision import landmark_indices as idx
from src.vision.eye_geometry import estimate_eyes
from src.vision.face_geometry import estimate_face_shape
from src.vision.face_landmarks import FaceLandmarks, LandmarkDetector, validate_landmarks
from src.vision.image_io import load_image
from src.vision.image_quality import GEOMETRY_CHECKS, QualityReport, assess_quality
from src.vision.regions import sampling_discs
from src.vision.skin_analysis import analyze_skin

logger = logging.getLogger(__name__)

OVERLAY_KEPT = (201, 130, 142)  # dusty rose
OVERLAY_EXCLUDED = (129, 116, 122)  # warm gray
OVERLAY_OUTLINE = (143, 101, 121)  # mauve


def render_overlay(rgb: np.ndarray, lm: FaceLandmarks, kept: tuple[str, ...],
                   long_side: int = SETTINGS.image.overlay_long_side) -> bytes:
    """Small JPEG showing the face outline and the skin sampling regions."""
    canvas = rgb.copy()
    thickness = max(1, round(max(rgb.shape[:2]) / 400))
    oval = np.round(lm.points[list(idx.FACE_OVAL)]).astype(np.int32)
    cv2.polylines(canvas, [oval], isClosed=True, color=OVERLAY_OUTLINE, thickness=thickness,
                  lineType=cv2.LINE_AA)
    for name, (center, radius) in sampling_discs(lm).items():
        color = OVERLAY_KEPT if name in kept else OVERLAY_EXCLUDED
        cv2.circle(canvas, (int(center[0]), int(center[1])), int(radius), color,
                   thickness * 2, lineType=cv2.LINE_AA)
    img = Image.fromarray(canvas)
    img.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _geometry_reasons(quality: QualityReport) -> tuple[str, ...]:
    return quality.messages(GEOMETRY_CHECKS, Severity.FAIL)


def analyze_image(data: bytes, detector: LandmarkDetector, *, with_overlay: bool = True
                  ) -> AnalysisResult:
    """Validate, detect, assess and estimate. Raises typed errors for unusable input."""
    started = time.perf_counter()
    decoded = load_image(data)
    faces = detector.detect(decoded.rgb)
    if not faces:
        raise FaceDetectionError(
            "no_face",
            "No face was found. Use a well-lit, front-facing photo with your whole face visible.")
    if len(faces) > 1:
        raise FaceDetectionError(
            "multiple_faces",
            "More than one face was found. Please use a photo with only your face in it.")
    lm = faces[0]
    validate_landmarks(lm)

    quality = assess_quality(decoded.rgb, lm)
    skin = analyze_skin(decoded.rgb, lm, quality)
    face_shape = estimate_face_shape(lm, quality.geometry_reliable, _geometry_reasons(quality))
    eye_reasons = _geometry_reasons(quality) or quality.messages(("eyes_open",), Severity.WARNING)
    eye_shape, eye_tilt = estimate_eyes(lm, quality.eyes_reliable, eye_reasons)

    overlay = render_overlay(decoded.rgb, lm, skin.kept_regions) if with_overlay else None
    result = AnalysisResult(
        image_fingerprint=decoded.fingerprint,
        image_size=decoded.size,
        quality_checks=quality.checks,
        features={SKIN_DEPTH: skin.depth, UNDERTONE: skin.undertone, EYE_SHAPE: eye_shape,
                  EYE_TILT: eye_tilt, FACE_SHAPE: face_shape},
        warnings=skin.warnings,
        overlay_jpeg=overlay,
    )
    # Log only timings and statuses — never pixels, landmarks or filenames.
    logger.info(
        "analysis completed in %.0f ms; statuses=%s",
        (time.perf_counter() - started) * 1000,
        {k: v.status.value for k, v in result.features.items()},
    )
    return result
