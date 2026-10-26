import pytest

from src.core.features import (
    FACE_SHAPE,
    FEATURE_NAMES,
    SKIN_DEPTH,
    AnalysisResult,
    FeatureEstimate,
    FeatureStatus,
    UserProfile,
)


def test_estimated_requires_allowed_value():
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.ESTIMATED, value="purple")
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.ESTIMATED, value=None)


def test_unknown_and_uncertain_carry_no_value():
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNKNOWN, value="light")
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN, value="light")
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNKNOWN, candidates=("light",))


def test_candidates_validated_and_deduplicated():
    est = FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN,
                          candidates=("light", "light", "medium"))
    assert est.candidates == ("light", "medium")
    assert est.possible_values == ("light", "medium")
    assert not est.usable
    with pytest.raises(ValueError):
        FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN, candidates=("oval",))


def test_confirmed_copy_keeps_measurements():
    est = FeatureEstimate(FACE_SHAPE, FeatureStatus.ESTIMATED, value="oval",
                          measurements={"length_ratio": 1.3})
    conf = est.confirmed("round")
    assert conf.status is FeatureStatus.USER_CONFIRMED and conf.value == "round"
    assert conf.measurements["length_ratio"] == 1.3
    assert conf.usable


def test_unknown_feature_name_rejected():
    with pytest.raises(ValueError):
        FeatureEstimate("hair_colour", FeatureStatus.UNKNOWN)


def test_profile_fills_missing_features_as_unknown():
    profile = UserProfile()
    assert set(profile.features) == set(FEATURE_NAMES)
    assert profile.is_empty
    updated = profile.with_feature(FeatureEstimate.user_set(SKIN_DEPTH, "tan"))
    assert updated.get(SKIN_DEPTH).value == "tan" and not updated.is_empty
    assert profile.get(SKIN_DEPTH).status is FeatureStatus.UNKNOWN  # immutable


def test_analysis_result_requires_all_features():
    with pytest.raises(ValueError):
        AnalysisResult("fp", (1, 1), (), {SKIN_DEPTH: FeatureEstimate.unknown(SKIN_DEPTH)})
    full = {n: FeatureEstimate.unknown(n) for n in FEATURE_NAMES}
    res = AnalysisResult("fp", (1, 1), (), full)
    assert set(res.unreliable_features) == set(FEATURE_NAMES)
