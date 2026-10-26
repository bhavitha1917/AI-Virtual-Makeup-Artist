import numpy as np
import pytest

from src.core.errors import LandmarkValidationError
from src.vision.face_landmarks import FaceLandmarks, MediaPipeFaceLandmarker, validate_landmarks
from tests.helpers import make_landmarks


def test_valid_synthetic_landmarks_pass():
    validate_landmarks(make_landmarks())


def test_too_few_landmarks():
    lm = make_landmarks()
    short = FaceLandmarks(points=lm.points[:100], image_size=lm.image_size)
    with pytest.raises(LandmarkValidationError) as exc:
        validate_landmarks(short)
    assert exc.value.code == "landmarks_incomplete"


def test_non_finite_landmarks():
    lm = make_landmarks()
    pts = lm.points.copy()
    pts[152] = np.nan
    with pytest.raises(LandmarkValidationError) as exc:
        validate_landmarks(FaceLandmarks(points=pts, image_size=lm.image_size))
    assert exc.value.code == "landmarks_non_finite"


def test_out_of_bounds_landmarks():
    lm = make_landmarks()
    pts = lm.points.copy()
    pts[10] = (400, -500)
    with pytest.raises(LandmarkValidationError) as exc:
        validate_landmarks(FaceLandmarks(points=pts, image_size=lm.image_size))
    assert exc.value.code == "landmarks_out_of_bounds"


def test_degenerate_iod():
    lm = make_landmarks(cheek=10.0)
    with pytest.raises(LandmarkValidationError) as exc:
        validate_landmarks(lm)
    assert exc.value.code == "landmarks_degenerate"


def test_pose_measures():
    assert make_landmarks().yaw_asymmetry == pytest.approx(1.0, abs=1e-6)
    assert make_landmarks(yaw_ratio=1.5).yaw_asymmetry == pytest.approx(1.5, rel=1e-6)
    assert make_landmarks(roll_deg=12).roll_degrees == pytest.approx(12, abs=1e-6)


def test_real_model_finds_no_face_in_synthetic_image(model_path):
    detector = MediaPipeFaceLandmarker(model_path)
    try:
        blank = np.full((480, 640, 3), 200, np.uint8)
        assert detector.detect(blank) == []
    finally:
        detector.close()


def test_real_model_rejects_wrong_dtype(model_path):
    detector = MediaPipeFaceLandmarker(model_path)
    try:
        with pytest.raises(ValueError):
            detector.detect(np.zeros((10, 10), np.float32))
    finally:
        detector.close()


def test_missing_linux_system_library_is_reported_as_model_load_failed(model_path, monkeypatch):
    """Regression: on Linux, MediaPipe loads libmediapipe.so (which needs libEGL.so.1 and
    libGLESv2.so.2) inside create_from_options; a missing library must be diagnosable."""
    from mediapipe.tasks.python import vision

    from src.core.errors import ModelUnavailableError

    def missing_lib(options):
        raise OSError("libEGL.so.1: cannot open shared object file: No such file or directory")

    monkeypatch.setattr(vision.FaceLandmarker, "create_from_options", missing_lib)
    with pytest.raises(ModelUnavailableError) as exc:
        MediaPipeFaceLandmarker(model_path)
    assert exc.value.code == "model_load_failed"
    assert exc.value.details.startswith("OSError: libEGL.so.1")
    assert "packages.txt" in exc.value.details


def test_packages_txt_lists_mediapipe_linux_runtime_libraries():
    """libmediapipe.so (mediapipe 1.1.1, manylinux) links libEGL.so.1 and libGLESv2.so.2;
    OpenCV needs libGL and GLib. Streamlit Community Cloud installs these from packages.txt."""
    from tests.conftest import ROOT

    packages = set((ROOT / "packages.txt").read_text(encoding="utf-8").split())
    assert {"libegl1", "libgles2", "libgl1", "libglib2.0-0"} <= packages
