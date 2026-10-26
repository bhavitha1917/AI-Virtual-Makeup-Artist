"""Synthetic landmarks, synthetic face images and a fake detector for tests.

The landmark builder places only the MediaPipe indices the vision engine uses, with
geometry controlled by explicit ratios, so expected classifications are known exactly.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from src.vision import landmark_indices as idx
from src.vision.face_landmarks import FaceLandmarks


@dataclass
class FaceSpec:
    width: int = 800
    height: int = 1000
    cx: float = 400.0
    cy: float = 520.0
    cheek: float = 360.0
    length_ratio: float = 1.30
    forehead_ratio: float = 0.88
    jaw_ratio: float = 0.80
    chin_angle: float = 107.0
    eye_open: float = 0.22
    eye_taper: float = 0.88
    lid_space: float = 0.44
    tilt_deg: float = 0.0
    left_eye_open: float | None = None  # override for asymmetric tests
    left_tilt_deg: float | None = None
    roll_deg: float = 0.0
    yaw_ratio: float = 1.0
    blink: float = 0.0


def _ellipse(center, rx, ry, n, start=0.0):
    t = np.linspace(start, start + 2 * np.pi, n, endpoint=False)
    return np.stack([center[0] + rx * np.cos(t), center[1] + ry * np.sin(t)], axis=1)


def make_landmarks(spec: FaceSpec | None = None, **overrides) -> FaceLandmarks:
    s = spec or FaceSpec()
    for k, v in overrides.items():
        setattr(s, k, v)
    pts = np.tile([s.cx, s.cy], (idx.NUM_LANDMARKS, 1)).astype(float)
    cheek, length = s.cheek, s.length_ratio * s.cheek
    top, chin_y = s.cy - length / 2, s.cy + length / 2

    # Face oval: generic ellipse, then exact key points.
    pts[list(idx.FACE_OVAL)] = _ellipse((s.cx, s.cy), cheek / 2, length / 2, len(idx.FACE_OVAL),
                                        start=-np.pi / 2)
    pts[idx.FOREHEAD_TOP] = (s.cx, top)
    pts[idx.CHIN] = (s.cx, chin_y)
    pts[idx.RIGHT_FACE_EDGE] = (s.cx - cheek / 2, s.cy - 0.02 * length)
    pts[idx.LEFT_FACE_EDGE] = (s.cx + cheek / 2, s.cy - 0.02 * length)
    fw = s.forehead_ratio * cheek
    pts[idx.RIGHT_FOREHEAD] = (s.cx - fw / 2, s.cy - 0.36 * length)
    pts[idx.LEFT_FOREHEAD] = (s.cx + fw / 2, s.cy - 0.36 * length)
    jw = s.jaw_ratio * cheek
    jaw_y = chin_y - (jw / 2) / math.tan(math.radians(s.chin_angle / 2))
    pts[idx.RIGHT_JAW] = (s.cx - jw / 2, jaw_y)
    pts[idx.LEFT_JAW] = (s.cx + jw / 2, jaw_y)

    # Nose tip positioned to produce the requested yaw ratio d(1,234)/d(1,454).
    x_r, x_l = pts[idx.RIGHT_FACE_EDGE][0], pts[idx.LEFT_FACE_EDGE][0]
    r = s.yaw_ratio
    pts[idx.NOSE_TIP] = ((x_r + r * x_l) / (1 + r), s.cy - 0.02 * length)

    pts[idx.RIGHT_CHEEK_CENTER] = (s.cx - 0.25 * cheek, s.cy + 0.06 * length)
    pts[idx.LEFT_CHEEK_CENTER] = (s.cx + 0.25 * cheek, s.cy + 0.06 * length)
    pts[idx.FOREHEAD_CENTER] = (s.cx, s.cy - 0.30 * length)

    iod, w_eye, eye_y = 0.45 * cheek, 0.20 * cheek, s.cy - 0.12 * length
    for eye, sign, contour, brow, opening, tilt in (
        (idx.RIGHT_EYE, -1, idx.RIGHT_EYE_CONTOUR, idx.RIGHT_BROW, s.eye_open, s.tilt_deg),
        (idx.LEFT_EYE, 1, idx.LEFT_EYE_CONTOUR, idx.LEFT_BROW,
         s.left_eye_open if s.left_eye_open is not None else s.eye_open,
         s.left_tilt_deg if s.left_tilt_deg is not None else s.tilt_deg),
    ):
        ex = s.cx + sign * iod / 2
        pts[list(contour)] = _ellipse((ex, eye_y), w_eye / 2, max(opening * w_eye / 2, 0.5),
                                      len(contour))
        dy = (w_eye / 2) * math.tan(math.radians(tilt))
        outer = np.array([ex + sign * w_eye / 2, eye_y - dy])
        inner = np.array([ex - sign * w_eye / 2, eye_y + dy])
        pts[eye["outer"]], pts[eye["inner"]] = outer, inner
        for frac, up, lo in zip((0.25, 0.5, 0.75), eye["upper"], eye["lower"], strict=True):
            base = outer + (inner - outer) * frac
            gap = opening * w_eye * (1.0 if frac == 0.5 else s.eye_taper)
            pts[up] = base - (0, gap / 2)
            pts[lo] = base + (0, gap / 2)
        upper_mid = pts[eye["upper"][1]]
        pts[eye["brow"]] = upper_mid - (0, s.lid_space * w_eye)
        brow_pts = [i for i in brow if i != eye["brow"]]
        xs = np.linspace(ex - w_eye * 0.6, ex + w_eye * 0.6, len(brow_pts))
        pts[brow_pts] = np.stack([xs, np.full_like(xs, pts[eye["brow"]][1] - 4)], axis=1)

    pts[list(idx.LIPS_OUTER)] = _ellipse((s.cx, s.cy + 0.30 * length), 0.20 * cheek,
                                         0.05 * length, len(idx.LIPS_OUTER))
    if s.roll_deg:
        t = math.radians(s.roll_deg)
        rot = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
        pts = (pts - (s.cx, s.cy)) @ rot.T + (s.cx, s.cy)
    shapes = {"eyeBlinkLeft": s.blink, "eyeBlinkRight": s.blink}
    return FaceLandmarks(points=pts, image_size=(s.width, s.height), blendshapes=shapes)


def make_face_image(lm: FaceLandmarks, skin_rgb=(205, 160, 128), background=(200, 200, 200),
                    noise_sigma: float = 6.0, seed: int = 0) -> np.ndarray:
    """Background + skin-coloured face hull + darker eyes/brows/lips, with mild noise."""
    w, h = lm.image_size
    img = np.empty((h, w, 3), np.float32)
    img[:] = background
    oval = np.round(lm.points[list(idx.FACE_OVAL)]).astype(np.int32)
    cv2.fillConvexPoly(img, cv2.convexHull(oval), tuple(float(c) for c in skin_rgb))
    for contour, color in ((idx.RIGHT_EYE_CONTOUR, (40, 30, 30)),
                           (idx.LEFT_EYE_CONTOUR, (40, 30, 30)),
                           (idx.RIGHT_BROW, (60, 40, 30)), (idx.LEFT_BROW, (60, 40, 30)),
                           (idx.LIPS_OUTER, (170, 70, 80))):
        poly = np.round(lm.points[list(contour)]).astype(np.int32)
        cv2.fillConvexPoly(img, cv2.convexHull(poly), color)
    rng = np.random.default_rng(seed)
    img += rng.normal(0, noise_sigma, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def encode(rgb: np.ndarray, fmt: str = "PNG", **kwargs) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format=fmt, **kwargs)
    return buf.getvalue()


class FakeDetector:
    """Returns predetermined faces; records calls."""

    def __init__(self, faces: list[FaceLandmarks]) -> None:
        self.faces = faces
        self.calls = 0

    def detect(self, rgb: np.ndarray) -> list[FaceLandmarks]:
        self.calls += 1
        h, w = rgb.shape[:2]
        return [FaceLandmarks(points=f.points * (w / f.image_size[0], h / f.image_size[1]),
                              image_size=(w, h), blendshapes=f.blendshapes) for f in self.faces]
