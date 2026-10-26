import numpy as np
import pytest

from src.core.features import FeatureStatus
from src.vision.face_geometry import (
    compute_face_measurements,
    estimate_face_shape,
    trapezoid,
)
from src.vision.face_landmarks import FaceLandmarks
from tests.helpers import make_landmarks


def test_trapezoid():
    assert trapezoid(0, 1, 2, 3, 4) == 0
    assert trapezoid(1.5, 1, 2, 3, 4) == pytest.approx(0.5)
    assert trapezoid(2.5, 1, 2, 3, 4) == 1
    assert trapezoid(3.5, 1, 2, 3, 4) == pytest.approx(0.5)
    assert trapezoid(5, 1, 2, 3, 4) == 0


def test_measurements_are_scale_invariant():
    small = compute_face_measurements(make_landmarks(cheek=300))
    large = compute_face_measurements(make_landmarks(cheek=420))
    assert small.length_ratio == pytest.approx(large.length_ratio, rel=1e-6)
    assert small.jaw_ratio == pytest.approx(large.jaw_ratio, rel=1e-6)
    assert small.chin_angle == pytest.approx(large.chin_angle, rel=1e-6)


def test_measurements_are_roll_invariant():
    a = compute_face_measurements(make_landmarks())
    b = compute_face_measurements(make_landmarks(roll_deg=15))
    assert a.length_ratio == pytest.approx(b.length_ratio, rel=1e-6)


@pytest.mark.parametrize("params, expected", [
    ({}, "oval"),
    ({"length_ratio": 1.05, "jaw_ratio": 0.85, "chin_angle": 125}, "round"),
    ({"length_ratio": 1.05, "jaw_ratio": 0.98, "chin_angle": 125}, "square"),
    ({"forehead_ratio": 0.95, "jaw_ratio": 0.75, "chin_angle": 95}, "heart"),
    ({"length_ratio": 1.60}, "oblong"),
])
def test_prototype_shapes(params, expected):
    est = estimate_face_shape(make_landmarks(**params), reliable=True)
    assert est.status is FeatureStatus.ESTIMATED, est
    assert est.value == expected


def test_between_categories_is_uncertain():
    est = estimate_face_shape(make_landmarks(length_ratio=1.42), reliable=True)
    assert est.status is FeatureStatus.UNCERTAIN
    assert set(est.candidates) == {"oval", "oblong"}


def test_unreliable_pose_gives_unknown():
    est = estimate_face_shape(make_landmarks(), reliable=False, unreliable_reasons=("turned",))
    assert est.status is FeatureStatus.UNKNOWN and est.reasons == ("turned",)


def test_degenerate_geometry_no_division_by_zero():
    pts = np.zeros((478, 2))
    est = estimate_face_shape(FaceLandmarks(points=pts, image_size=(100, 100)), reliable=True)
    assert est.status is FeatureStatus.UNKNOWN


def test_jaw_coincident_with_chin_is_unknown():
    lm = make_landmarks()
    pts = lm.points.copy()
    pts[172] = pts[152]
    est = estimate_face_shape(FaceLandmarks(points=pts, image_size=lm.image_size), reliable=True)
    assert est.status is FeatureStatus.UNKNOWN


def test_stable_on_repeated_input():
    lm = make_landmarks()
    assert estimate_face_shape(lm, True) == estimate_face_shape(lm, True)
