import dataclasses

import cv2
import numpy as np
import pytest

from src.core.errors import FaceDetectionError, ImageValidationError, LandmarkValidationError
from src.core.features import FEATURE_NAMES, FeatureStatus
from src.vision.face_landmarks import FaceLandmarks, MediaPipeFaceLandmarker
from src.vision.pipeline import analyze_image
from tests.helpers import FakeDetector, encode, make_face_image, make_landmarks


@pytest.fixture
def face():
    lm = make_landmarks()
    return lm, make_face_image(lm)


def test_valid_face_produces_full_result(face):
    lm, img = face
    result = analyze_image(encode(img), FakeDetector([lm]))
    assert set(result.features) == set(FEATURE_NAMES)
    assert result.features["face_shape"].value == "oval"
    assert result.features["eye_shape"].value == "almond"
    assert result.overlay_jpeg[:2] == b"\xff\xd8"  # JPEG
    assert all(c.severity.value == "ok" for c in result.quality_checks)


def test_result_holds_no_original_pixels(face):
    lm, img = face
    result = analyze_image(encode(img), FakeDetector([lm]), with_overlay=False)
    for f in dataclasses.fields(result):
        assert not isinstance(getattr(result, f.name), np.ndarray)
    assert result.overlay_jpeg is None


def test_no_face(face):
    _, img = face
    with pytest.raises(FaceDetectionError) as exc:
        analyze_image(encode(img), FakeDetector([]))
    assert exc.value.code == "no_face"


def test_multiple_faces(face):
    lm, img = face
    with pytest.raises(FaceDetectionError) as exc:
        analyze_image(encode(img), FakeDetector([lm, lm]))
    assert exc.value.code == "multiple_faces"


def test_invalid_image_never_reaches_detector():
    detector = FakeDetector([])
    with pytest.raises(ImageValidationError):
        analyze_image(b"not an image", detector)
    assert detector.calls == 0


def test_invalid_landmarks(face):
    lm, img = face
    bad = FaceLandmarks(points=np.full_like(lm.points, np.nan), image_size=lm.image_size)
    with pytest.raises(LandmarkValidationError):
        analyze_image(encode(img), FakeDetector([bad]))


def test_poor_quality_image_reports_unknown_skin_without_inventing(face):
    lm, img = face
    blurred = cv2.GaussianBlur(img, (0, 0), 12)
    result = analyze_image(encode(blurred), FakeDetector([lm]))
    assert result.features["skin_depth"].status is FeatureStatus.UNKNOWN
    assert result.features["skin_depth"].value is None
    assert "skin_depth" in result.unreliable_features


def test_turned_head_gives_unknown_geometry():
    lm = make_landmarks(yaw_ratio=2.0)
    result = analyze_image(encode(make_face_image(lm)), FakeDetector([lm]))
    assert result.features["face_shape"].status is FeatureStatus.UNKNOWN
    assert result.features["eye_shape"].status is FeatureStatus.UNKNOWN


def test_real_model_no_face_end_to_end(model_path):
    detector = MediaPipeFaceLandmarker(model_path)
    try:
        img = np.full((600, 800, 3), 210, np.uint8)
        with pytest.raises(FaceDetectionError) as exc:
            analyze_image(encode(img), detector)
        assert exc.value.code == "no_face"
    finally:
        detector.close()
