import cv2
import numpy as np

from src.core.features import Severity
from src.vision.image_quality import assess_quality
from tests.helpers import make_face_image, make_landmarks


def sev(report, check_id):
    return next(c.severity for c in report.checks if c.check_id == check_id)


def test_good_synthetic_image_passes_all_checks():
    lm = make_landmarks()
    report = assess_quality(make_face_image(lm), lm)
    assert all(c.severity is Severity.OK for c in report.checks), report.checks
    assert report.skin_reliable and report.geometry_reliable and report.eyes_reliable


def test_blurry_image_fails_sharpness():
    lm = make_landmarks()
    img = cv2.GaussianBlur(make_face_image(lm), (0, 0), 12)
    report = assess_quality(img, lm)
    assert sev(report, "sharpness") is Severity.FAIL
    assert not report.skin_reliable


def test_dark_image_fails_exposure():
    lm = make_landmarks()
    report = assess_quality(make_face_image(lm, skin_rgb=(40, 30, 25), noise_sigma=2), lm)
    assert sev(report, "exposure") is Severity.FAIL
    assert "too dark" in next(c.message for c in report.checks if c.check_id == "exposure")


def test_overexposed_image_flags_highlights():
    lm = make_landmarks()
    report = assess_quality(make_face_image(lm, skin_rgb=(255, 255, 255), noise_sigma=1), lm)
    assert sev(report, "highlights") is Severity.FAIL
    assert sev(report, "exposure") is Severity.FAIL


def test_uneven_lighting_detected():
    lm = make_landmarks()
    img = make_face_image(lm).astype(np.float32)
    img[:, : img.shape[1] // 2] *= 0.55  # darken the subject's right side
    report = assess_quality(img.clip(0, 255).astype(np.uint8), lm)
    assert sev(report, "lighting_balance") is Severity.FAIL


def test_small_face_fails():
    lm = make_landmarks(cheek=100.0)
    report = assess_quality(make_face_image(lm), lm)
    assert sev(report, "face_size") is Severity.FAIL
    assert not report.geometry_reliable


def test_turned_head_fails_geometry():
    lm = make_landmarks(yaw_ratio=2.0)
    report = assess_quality(make_face_image(lm), lm)
    assert sev(report, "head_yaw") is Severity.FAIL
    assert not report.geometry_reliable


def test_blink_makes_eyes_unreliable_only():
    lm = make_landmarks(blink=0.9)
    report = assess_quality(make_face_image(lm), lm)
    assert sev(report, "eyes_open") is Severity.WARNING
    assert report.geometry_reliable and not report.eyes_reliable
