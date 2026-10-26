from src.core.features import (
    EYE_SHAPE,
    FEATURE_NAMES,
    SKIN_DEPTH,
    AnalysisResult,
    FeatureEstimate,
    FeatureStatus,
    UserProfile,
)
from src.routine.inventory import create_custom_item
from src.routine.routine_generator import RoutineRequest, generate_routine, request_signature
from src.ui import state


def analysis(fp="fp-1", depth="medium"):
    feats = {n: FeatureEstimate.unknown(n) for n in FEATURE_NAMES}
    feats[SKIN_DEPTH] = FeatureEstimate(SKIN_DEPTH, FeatureStatus.ESTIMATED, value=depth)
    return AnalysisResult(fp, (100, 100), (), feats, overlay_jpeg=b"jpeg")


def fresh():
    ss = {}
    state.init_state(ss)
    return ss


def test_init_defaults():
    ss = fresh()
    assert state.get_analysis(ss) is None and state.get_inventory(ss) == ()
    assert state.get_profile(ss).is_empty
    assert state.has_entered(ss) is False


def test_enter_studio_persists_and_init_does_not_reset_it():
    ss = fresh()
    state.enter_studio(ss)
    state.init_state(ss)  # runs on every rerun
    assert state.has_entered(ss) is True


def test_analysis_sets_profile():
    ss = fresh()
    state.set_analysis(ss, analysis())
    assert state.get_profile(ss).source == "analysis"
    assert state.get_profile(ss).get(SKIN_DEPTH).value == "medium"


def test_new_image_clears_stale_analysis_and_profile():
    ss = fresh()
    state.note_image(ss, "fp-1")
    state.set_analysis(ss, analysis("fp-1"))
    assert state.note_image(ss, "fp-1") is False  # same photo: keep
    assert state.get_analysis(ss) is not None
    assert state.note_image(ss, "fp-2") is True  # different photo: clear
    assert state.get_analysis(ss) is None
    assert state.get_profile(ss).is_empty


def test_empty_widget_does_not_clear_results():
    ss = fresh()
    state.set_analysis(ss, analysis("fp-1"))
    assert state.note_image(ss, None) is False
    assert state.get_analysis(ss) is not None


def test_clear_analysis_resets_widgets_and_overlay():
    ss = fresh()
    state.set_analysis(ss, analysis())
    nonce = ss[state.UPLOADER_NONCE]
    state.clear_analysis(ss)
    assert state.get_analysis(ss) is None
    assert ss[state.UPLOADER_NONCE] == nonce + 1
    assert state.uploader_key(ss, "u") == f"u_{nonce + 1}"


def test_manual_profile_survives_clearing_analysis():
    ss = fresh()
    state.confirm_features(ss, {SKIN_DEPTH: "tan"})
    state.clear_analysis(ss)
    assert state.get_profile(ss).get(SKIN_DEPTH).value == "tan"


def test_confirm_features_marks_confirmed_and_clears():
    ss = fresh()
    state.set_analysis(ss, analysis())
    profile = state.confirm_features(ss, {SKIN_DEPTH: "tan", EYE_SHAPE: None})
    assert profile.get(SKIN_DEPTH).status is FeatureStatus.USER_CONFIRMED
    assert profile.get(SKIN_DEPTH).value == "tan"
    assert profile.get(EYE_SHAPE).status is FeatureStatus.UNKNOWN


def test_untouched_uncertain_feature_is_preserved():
    ss = fresh()
    uncertain = FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN, candidates=("light", "medium"))
    ss[state.PROFILE] = UserProfile({SKIN_DEPTH: uncertain}, source="analysis")
    profile = state.confirm_features(ss, {SKIN_DEPTH: None})
    assert profile.get(SKIN_DEPTH) == uncertain


def test_confirm_features_rejects_invalid():
    ss = fresh()
    import pytest

    with pytest.raises(ValueError):
        state.confirm_features(ss, {SKIN_DEPTH: "lavender"})
    with pytest.raises(ValueError):
        state.confirm_features(ss, {"hair": "x"})


def test_analysis_error_scoped_to_fingerprint():
    ss = fresh()
    state.set_analysis_error(ss, "fp-1", "no_face", "No face")
    assert state.get_analysis_error(ss, "fp-1")["code"] == "no_face"
    assert state.get_analysis_error(ss, "fp-2") is None
    state.note_image(ss, "fp-2")
    assert ss[state.ANALYSIS_ERROR] is None


def test_stale_routine_hidden(production_rules):
    ss = fresh()
    inv = (create_custom_item(category="lipstick", product_name="Red"),)
    req = RoutineRequest(inv, "everyday")
    state.store_routine(ss, generate_routine(req, production_rules))
    sig = request_signature(req)
    assert state.current_routine(ss, sig) is not None
    changed = request_signature(RoutineRequest(inv, "glam"))
    assert state.current_routine(ss, changed) is None
    assert state.routine_is_stale(ss, changed)


def test_sessions_are_independent():
    a, b = fresh(), fresh()
    state.set_inventory(a, (create_custom_item(category="lipstick", product_name="Red"),))
    assert state.get_inventory(b) == ()
    assert isinstance(state.get_profile(b), UserProfile)


def test_flash_is_one_shot():
    ss = fresh()
    state.flash(ss, "hello")
    assert state.flash(ss) == "hello"
    assert state.flash(ss) is None
