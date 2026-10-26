import numpy as np
import pytest

from src.core.features import FeatureStatus
from src.vision import landmark_indices as idx
from src.vision.eye_geometry import estimate_eyes, measure_eye
from tests.helpers import make_landmarks


@pytest.mark.parametrize("params, expected", [
    ({}, "almond"),
    ({"eye_open": 0.36, "eye_taper": 0.95, "lid_space": 0.5}, "round"),
    ({"lid_space": 0.28}, "hooded"),
])
def test_eye_shapes(params, expected):
    shape, _ = estimate_eyes(make_landmarks(**params), reliable=True)
    assert shape.status is FeatureStatus.ESTIMATED and shape.value == expected


def test_monolid_never_auto_assigned():
    for params in ({}, {"eye_open": 0.36, "eye_taper": 0.95}, {"lid_space": 0.2}):
        shape, _ = estimate_eyes(make_landmarks(**params), reliable=True)
        assert shape.value != "monolid" and "monolid" not in shape.candidates


def test_closed_eyes_unknown():
    shape, _ = estimate_eyes(make_landmarks(eye_open=0.05), reliable=True)
    assert shape.status is FeatureStatus.UNKNOWN


def test_eyes_disagree_is_uncertain():
    shape, _ = estimate_eyes(make_landmarks(left_eye_open=0.36, eye_taper=0.88), reliable=True)
    assert shape.status is FeatureStatus.UNCERTAIN
    assert "almond" in shape.candidates


def test_single_ratio_is_not_enough():
    # Same opening as a typical almond eye but untapered ends: neither almond nor round.
    shape, _ = estimate_eyes(make_landmarks(eye_open=0.25, eye_taper=1.0), reliable=True)
    assert shape.status is FeatureStatus.UNCERTAIN


@pytest.mark.parametrize("tilt, expected", [(0, "neutral"), (7, "upturned"), (-7, "downturned")])
def test_tilt(tilt, expected):
    _, est = estimate_eyes(make_landmarks(tilt_deg=tilt), reliable=True)
    assert est.status is FeatureStatus.ESTIMATED and est.value == expected


def test_tilt_between_bands_uncertain():
    _, est = estimate_eyes(make_landmarks(tilt_deg=3.2), reliable=True)
    assert est.status is FeatureStatus.UNCERTAIN
    assert est.candidates == ("neutral", "upturned")


def test_tilt_is_roll_corrected():
    _, est = estimate_eyes(make_landmarks(roll_deg=15), reliable=True)
    assert est.value == "neutral"


def test_tilt_disagreement_uncertain():
    _, est = estimate_eyes(make_landmarks(tilt_deg=0, left_tilt_deg=8), reliable=True)
    assert est.status is FeatureStatus.UNCERTAIN


def test_unreliable_gives_unknown():
    shape, tilt = estimate_eyes(make_landmarks(), reliable=False)
    assert shape.status is FeatureStatus.UNKNOWN and tilt.status is FeatureStatus.UNKNOWN


def test_zero_width_eye_is_handled():
    pts = np.zeros((478, 2))
    assert measure_eye(pts, idx.RIGHT_EYE) is None
