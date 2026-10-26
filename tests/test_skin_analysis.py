import cv2
import numpy as np
import pytest

from src.config import SkinThresholds
from src.core.features import FeatureStatus
from src.vision.image_quality import assess_quality
from src.vision.regions import rgb_to_lab, sampling_discs
from src.vision.skin_analysis import (
    analyze_skin,
    classify_depth,
    classify_undertone,
    dominant_cluster_delta,
    hue_angle,
    ita_degrees,
    screen_regions,
)
from tests.helpers import make_face_image, make_landmarks


def test_lab_conversion_matches_reference_values():
    lab = rgb_to_lab(np.array([[255, 255, 255], [255, 0, 0], [0, 0, 0]], np.uint8))
    assert lab[0] == pytest.approx([100, 0, 0], abs=0.5)
    assert lab[1] == pytest.approx([53.24, 80.09, 67.20], abs=0.5)  # sRGB red, D65
    assert lab[2] == pytest.approx([0, 0, 0], abs=0.5)


def test_ita_and_hue_maths():
    assert ita_degrees(50, 20) == pytest.approx(0.0)
    assert ita_degrees(70, 20) == pytest.approx(45.0)
    assert hue_angle(10, 10) == pytest.approx(45.0)
    assert hue_angle(0, 10) == pytest.approx(90.0)


@pytest.mark.parametrize("ita, expected", [
    (60, "fair"), (48, "light"), (34, "medium"), (19, "tan"), (-10, "deep"), (-45, "rich"),
])
def test_depth_bands(ita, expected):
    est = classify_depth(ita, [ita, ita], b_star=18)
    assert est.status is FeatureStatus.ESTIMATED and est.value == expected


def test_depth_near_boundary_is_uncertain():
    est = classify_depth(54.0, [54.0, 54.0], b_star=18)
    assert est.status is FeatureStatus.UNCERTAIN
    assert est.candidates == ("fair", "light")
    assert est.value is None


def test_depth_region_spread_is_uncertain():
    est = classify_depth(35.0, [20.0, 45.0], b_star=18)
    assert est.status is FeatureStatus.UNCERTAIN
    assert set(est.candidates) == {"light", "medium", "tan"}


def test_depth_unknown_without_yellow_component():
    assert classify_depth(40, [40], b_star=-2).status is FeatureStatus.UNKNOWN


@pytest.mark.parametrize("hue, expected", [(45, "cool"), (56, "neutral"), (66, "warm")])
def test_undertone_bands(hue, expected):
    est = classify_undertone(hue, [hue, hue], cast_suspected=False, quality_warnings=())
    assert est.status is FeatureStatus.ESTIMATED and est.value == expected


def test_undertone_boundary_uncertain():
    est = classify_undertone(51.0, [51.0], cast_suspected=False, quality_warnings=())
    assert est.status is FeatureStatus.UNCERTAIN and est.candidates == ("cool", "neutral")


@pytest.mark.parametrize("kwargs", [
    {"cast_suspected": True, "quality_warnings": ()},
    {"cast_suspected": False, "quality_warnings": ("Lighting is uneven.",)},
])
def test_undertone_uncertain_on_cast_or_quality_warning(kwargs):
    est = classify_undertone(66.0, [66.0], **kwargs)
    assert est.status is FeatureStatus.UNCERTAIN
    assert "warm" in est.candidates


def test_undertone_uncertain_when_regions_disagree():
    est = classify_undertone(56.0, [48.0, 64.0], cast_suspected=False, quality_warnings=())
    assert est.status is FeatureStatus.UNCERTAIN


def test_pipeline_measures_painted_skin_not_lips_or_eyes():
    skin = (205, 160, 128)
    lm = make_landmarks()
    img = make_face_image(lm, skin_rgb=skin, noise_sigma=3)
    result = analyze_skin(img, lm, assess_quality(img, lm))
    expected = rgb_to_lab(np.array([skin], np.uint8))[0]
    m = result.measurements
    assert [m["L_star"], m["a_star"], m["b_star"]] == pytest.approx(list(expected), abs=1.5)
    assert result.depth.status in (FeatureStatus.ESTIMATED, FeatureStatus.UNCERTAIN)
    assert set(result.kept_regions) == {"left_cheek", "right_cheek", "forehead"}


def test_obstructed_region_is_excluded():
    lm = make_landmarks()
    img = make_face_image(lm, noise_sigma=3)
    center, radius = sampling_discs(lm)["forehead"]
    cv2.circle(img, (int(center[0]), int(center[1])), int(radius * 1.5), (45, 32, 28), -1)
    result = analyze_skin(img, lm, assess_quality(img, lm))
    assert "forehead" in result.excluded_regions
    assert result.depth.status is not FeatureStatus.UNKNOWN
    assert any("ignored" in w for w in result.warnings)


def test_empty_regions_give_unknown():
    lm = make_landmarks()
    img = make_face_image(lm)
    tiny = SkinThresholds(cheek_radius_iod=0.001, forehead_radius_iod=0.001)
    result = analyze_skin(img, lm, assess_quality(img, lm), cfg=tiny)
    assert result.depth.status is FeatureStatus.UNKNOWN
    assert result.undertone.status is FeatureStatus.UNKNOWN


def test_unreliable_quality_gives_unknown_with_reason():
    lm = make_landmarks()
    img = cv2.GaussianBlur(make_face_image(lm), (0, 0), 12)
    result = analyze_skin(img, lm, assess_quality(img, lm))
    assert result.depth.status is FeatureStatus.UNKNOWN
    assert any("blurry" in r for r in result.depth.reasons)


def test_colour_cast_makes_undertone_uncertain():
    lm = make_landmarks()
    img = make_face_image(lm, background=(255, 140, 40))
    result = analyze_skin(img, lm, assess_quality(img, lm))
    assert result.undertone.status is FeatureStatus.UNCERTAIN
    assert any("colour cast" in r for r in result.undertone.reasons)


def test_screen_regions_requires_minimum_pixels():
    kept, excluded = screen_regions({"a": np.zeros((5, 3)), "b": np.zeros((500, 3))})
    assert "a" in excluded and "b" in kept


def test_kmeans_diagnostic_is_deterministic():
    rng = np.random.default_rng(1)
    pixels = rng.normal([60, 15, 20], 3, (2000, 3)).astype(np.float32)
    assert dominant_cluster_delta(pixels) == dominant_cluster_delta(pixels)
    assert dominant_cluster_delta(pixels[:10]) is None
