"""MediaPipe Face Landmarker wrapper and landmark validation."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from src.config import SETTINGS
from src.core.errors import LandmarkValidationError, ModelUnavailableError
from src.vision import landmark_indices as idx


@dataclass(frozen=True)
class FaceLandmarks:
    """Landmarks of one face in pixel coordinates of the analysed image."""

    points: np.ndarray  # float64 (N, 2): x, y in pixels
    image_size: tuple[int, int]  # (width, height)
    blendshapes: Mapping[str, float] = field(default_factory=dict)

    def __getitem__(self, i: int) -> np.ndarray:
        return self.points[i]

    def dist(self, a: int, b: int) -> float:
        return float(np.linalg.norm(self.points[a] - self.points[b]))

    def eye_center(self, eye: Mapping) -> np.ndarray:
        return (self.points[eye["outer"]] + self.points[eye["inner"]]) / 2.0

    @property
    def inter_ocular_distance(self) -> float:
        return float(np.linalg.norm(self.eye_center(idx.RIGHT_EYE) - self.eye_center(idx.LEFT_EYE)))

    @property
    def roll_degrees(self) -> float:
        """Angle of the line from the subject's right eye centre to the left eye centre."""
        r, lft = self.eye_center(idx.RIGHT_EYE), self.eye_center(idx.LEFT_EYE)
        return float(np.degrees(np.arctan2(lft[1] - r[1], lft[0] - r[0])))

    @property
    def yaw_asymmetry(self) -> float:
        """max(r, 1/r) for nose-to-edge distances; 1.0 is perfectly frontal."""
        right = self.dist(idx.NOSE_TIP, idx.RIGHT_FACE_EDGE)
        left = self.dist(idx.NOSE_TIP, idx.LEFT_FACE_EDGE)
        if min(right, left) <= 1e-6:
            return float("inf")
        ratio = right / left
        return float(max(ratio, 1.0 / ratio))


class LandmarkDetector(Protocol):
    def detect(self, rgb: np.ndarray) -> list[FaceLandmarks]: ...


def validate_landmarks(lm: FaceLandmarks, required: Iterable[int] = idx.REQUIRED_INDICES) -> None:
    """Raise ``LandmarkValidationError`` if landmarks are unusable for measurement."""
    pts = lm.points
    if pts.ndim != 2 or pts.shape[1] != 2 or pts.shape[0] < idx.MIN_LANDMARKS:
        raise LandmarkValidationError("landmarks_incomplete",
                                      details=f"shape {getattr(pts, 'shape', None)}")
    required = list(required)
    sub = pts[required]
    if not np.all(np.isfinite(sub)):
        raise LandmarkValidationError("landmarks_non_finite")
    w, h = lm.image_size
    margin = SETTINGS.geometry.landmark_bounds_margin
    if (np.any(sub[:, 0] < -margin * w) or np.any(sub[:, 0] > (1 + margin) * w) or
            np.any(sub[:, 1] < -margin * h) or np.any(sub[:, 1] > (1 + margin) * h)):
        raise LandmarkValidationError(
            "landmarks_out_of_bounds",
            "Part of the face is outside the photo. Make sure your whole face is in frame.",
        )
    if lm.inter_ocular_distance < SETTINGS.geometry.min_iod_px:
        raise LandmarkValidationError("landmarks_degenerate",
                                      "The face is too small to measure in this photo.")


class MediaPipeFaceLandmarker:
    """Thread-safe wrapper over MediaPipe's Face Landmarker (IMAGE mode)."""

    def __init__(self, model_path: Path, max_faces: int = SETTINGS.model.max_faces) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ModelUnavailableError("mediapipe_missing",
                                        "MediaPipe is not installed.") from exc
        self._mp = mp
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
            output_face_blendshapes=True,
        )
        try:
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
        except Exception as exc:  # MediaPipe raises RuntimeError/ValueError variants
            raise ModelUnavailableError(
                "model_load_failed", "The face-analysis model could not be loaded.",
                details=str(exc)) from exc
        self._lock = threading.Lock()

    def detect(self, rgb: np.ndarray) -> list[FaceLandmarks]:
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Expected an RGB uint8 image")
        h, w = rgb.shape[:2]
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                               data=np.ascontiguousarray(rgb))
        with self._lock:
            result = self._landmarker.detect(image)
        faces: list[FaceLandmarks] = []
        for i, landmarks in enumerate(result.face_landmarks):
            pts = np.array([[p.x * w, p.y * h] for p in landmarks], dtype=np.float64)
            shapes: dict[str, float] = {}
            if result.face_blendshapes and i < len(result.face_blendshapes):
                shapes = {c.category_name: float(c.score) for c in result.face_blendshapes[i]}
            faces.append(FaceLandmarks(points=pts, image_size=(w, h), blendshapes=shapes))
        return faces

    def close(self) -> None:
        with self._lock:
            self._landmarker.close()
