"""Streamlit AppTest smoke tests for every page and key interactions."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from src.core.enums import (
    Category,
    ColorFamily,
    ConcealerPurpose,
    CorrectionTarget,
    Finish,
    Formulation,
    Intensity,
)
from src.core.features import (
    EYE_SHAPE,
    FACE_SHAPE,
    SKIN_DEPTH,
    UNDERTONE,
    FeatureEstimate,
    FeatureStatus,
    UserProfile,
)
from src.ui import state
from tests.conftest import ROOT

PAGE_SCRIPT = """
import streamlit as st
from src.ui.navigation import build_navigation
from src.ui.state import init_state
from src.ui.theme import inject_theme
from src.ui.components import footer
inject_theme()
init_state(st.session_state)
build_navigation(default="{page}").run()
footer()
"""
TIMEOUT = 60


def open_page(page: str, **session) -> AppTest:
    at = AppTest.from_string(PAGE_SCRIPT.format(page=page), default_timeout=TIMEOUT)
    for k, v in session.items():
        at.session_state[k] = v
    return at.run()


def all_html(at: AppTest) -> str:
    """Rendered custom markup, excluding the injected stylesheet (it names every class)."""
    bodies = (getattr(getattr(h, "proto", None), "body", "") for h in at.get("html"))
    return " ".join(b for b in bodies if not b.lstrip().startswith("<style>"))


def welcome_background_injected(at: AppTest) -> bool:
    bodies = (getattr(getattr(h, "proto", None), "body", "") for h in at.get("html"))
    return any("background-image: url(data:image/png;base64," in b for b in bodies)


def no_errors(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]


def confirmed(name, value):
    return FeatureEstimate(name, FeatureStatus.USER_CONFIRMED, value=value)


def test_main_app_starts_on_welcome_screen():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=TIMEOUT).run()
    no_errors(at)
    text = all_html(at)
    assert "bs-welcome-brand" in text and "Beauty</span> <span>Studio" in text
    assert "Your Face, Your Shades, Your Beauty." in text
    assert [b.label for b in at.button] == ["Get Started →"]
    assert welcome_background_injected(at)
    assert "How it works" not in text and "Privacy" not in text  # no Home content, no footer
    assert at.session_state[state.ENTERED] is False


def test_enter_button_opens_existing_home():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=TIMEOUT).run()
    at.button(key="bs_enter").click().run()
    no_errors(at)
    assert at.session_state[state.ENTERED] is True
    text = all_html(at)
    assert "Your Face. Your Shades. Your Beauty." in text and "How it works" in text
    labels = [b.label for b in at.button]
    assert "Discover My Shades" in labels and "Create My Routine" in labels
    assert "Get Started →" not in labels
    assert not welcome_background_injected(at)
    assert "Privacy" in text  # footer


def test_entered_session_skips_welcome_and_navigates():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=TIMEOUT)
    at.session_state[state.ENTERED] = True
    at.run()
    no_errors(at)
    assert "How it works" in all_html(at)
    next(b for b in at.button if b.label == "Discover My Shades").click().run()
    no_errors(at)
    assert "Face Analysis" in all_html(at)
    assert "Get Started →" not in [b.label for b in at.button]


@pytest.mark.parametrize("page, marker", [
    ("home", "How it works"),
    ("analysis", "Face Analysis"),
    ("shades", "Shade Finder"),
    ("routine", "My Makeup Routine"),
    ("about", "How The Beauty Studio works"),
])
def test_every_page_renders(page, marker):
    at = open_page(page)
    no_errors(at)
    assert marker in all_html(at)


def test_face_analysis_empty_state_keeps_upload_option():
    at = open_page("analysis")
    no_errors(at)
    assert "No photo yet" in all_html(at)
    assert len(at.get("file_uploader")) == 1


def test_shade_finder_needs_depth_without_profile():
    at = open_page("shades")
    no_errors(at)
    text = all_html(at)
    assert "A little more information needed" in text
    assert "Demonstration catalog" in text


def test_shade_finder_shows_explained_cards_for_profile():
    profile = UserProfile({SKIN_DEPTH: confirmed(SKIN_DEPTH, "medium"),
                           UNDERTONE: confirmed(UNDERTONE, "warm")})
    at = open_page("shades", **{state.PROFILE: profile})
    no_errors(at)
    text = all_html(at)
    assert 'class="bs-product"' in text and "Listed depth" in text
    assert "not a probability" in text
    assert "Shade verification" in text


def test_shade_finder_eyeliner_shows_technique():
    profile = UserProfile({EYE_SHAPE: confirmed(EYE_SHAPE, "hooded")})
    at = open_page("shades", **{state.PROFILE: profile})
    at.get("button_group")[0].set_value("eyeliner").run()
    no_errors(at)
    assert "Technique for your eyes" in all_html(at)


def test_routine_add_custom_product_and_generate():
    at = open_page("routine")
    no_errors(at)
    assert "Your collection is empty" in all_html(at)
    at.text_input(key="bs_custom_name").set_value("My favourite red")
    at.selectbox(key="bs_custom_category").set_value(Category.LIPSTICK)
    next(b for b in at.button if b.label == "Add my product").click().run()
    no_errors(at)
    inv = at.session_state[state.INVENTORY]
    assert len(inv) == 1 and inv[0].product_name == "My favourite red"
    next(b for b in at.button if b.label == "Generate my routine").click().run()
    no_errors(at)
    text = all_html(at)
    assert 'class="bs-routine-step"' in text and "My favourite red" in text


def test_routine_stale_after_inventory_change():
    from src.routine.inventory import create_custom_item

    inv = (create_custom_item(category="lipstick", product_name="Red one"),)
    at = open_page("routine", **{state.INVENTORY: inv})
    next(b for b in at.button if b.label == "Generate my routine").click().run()
    assert 'class="bs-routine-step"' in all_html(at)
    next(b for b in at.button if b.label == "Remove").click().run()
    no_errors(at)
    text = all_html(at)
    assert 'class="bs-routine-step"' not in text
    assert "Your collection is empty" in text


def test_routine_uses_confirmed_features():
    from src.routine.inventory import create_custom_item

    inv = (create_custom_item(category="blush", product_name="Peachy"),)
    profile = UserProfile({FACE_SHAPE: confirmed(FACE_SHAPE, "round")})
    at = open_page("routine", **{state.INVENTORY: inv, state.PROFILE: profile})
    next(b for b in at.button if b.label == "Generate my routine").click().run()
    no_errors(at)
    assert "For your features" in all_html(at)


def test_model_failure_is_logged_and_shown_as_friendly_error(monkeypatch, caplog):
    import src.ui.navigation  # noqa: F401  (page modules import via navigation)
    from src.core.errors import ModelUnavailableError
    from src.ui.pages import face_analysis

    def unavailable():
        raise ModelUnavailableError("model_load_failed",
                                    "The face-analysis model could not be loaded.",
                                    details="OSError: libEGL.so.1: cannot open shared object file")

    monkeypatch.setattr(face_analysis, "get_detector", unavailable)
    ss: dict = {}
    with caplog.at_level("ERROR", logger=face_analysis.__name__):
        face_analysis._run_analysis(ss, b"image-bytes", "fp")
    assert "model_load_failed: OSError: libEGL.so.1" in caplog.text
    err = state.get_analysis_error(ss, "fp")
    assert err["message"] == "The face-analysis model could not be loaded."
    assert "libEGL" not in err["message"]


# ---- Shade Finder: Apply / Clear filters ----

def _fresh_profile():
    return UserProfile({SKIN_DEPTH: confirmed(SKIN_DEPTH, "medium"),
                        UNDERTONE: confirmed(UNDERTONE, "warm")})


def _cards(at: AppTest) -> int:
    return all_html(at).count('class="bs-product"')


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def test_shade_finder_shows_apply_and_clear_buttons():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    no_errors(at)
    labels = [b.label for b in at.button]
    assert "Apply Filters" in labels and "Clear Filters" in labels


def _summary(at: AppTest) -> str:
    return next(c.value for c in at.caption if "eligible shades" in c.value)


def _cards_html(at: AppTest) -> str:
    html = all_html(at)
    return html[html.index('class="bs-product"'):]


def test_shade_finder_selection_does_not_change_results_until_applied():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    before = _cards_html(at)
    at.selectbox(key="bs_sf_foundation_finish").set_value(Finish.DEWY).run()
    no_errors(at)
    assert _cards_html(at) == before  # an unsubmitted selection changes nothing
    at.selectbox(key="bs_sf_foundation_finish").set_value(Finish.DEWY)
    _button(at, "Apply Filters").click().run()
    no_errors(at)
    assert _cards_html(at) != before
    assert at.selectbox(key="bs_sf_foundation_finish").value == Finish.DEWY


def test_shade_finder_applied_filter_updates_result_count():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.get("button_group")[0].set_value(Category.CONCEALER).run()
    both = _summary(at)
    at.radio(key="bs_sf_concealer_purpose").set_value(ConcealerPurpose.SPOT).run()
    assert _summary(at) == both  # not applied yet
    at.radio(key="bs_sf_concealer_purpose").set_value(ConcealerPurpose.SPOT)
    _button(at, "Apply Filters").click().run()
    no_errors(at)
    spot = _summary(at)
    assert spot != both and "of 12 eligible" in spot


def test_shade_finder_clear_filters_restores_results():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    before = _cards_html(at)
    at.selectbox(key="bs_sf_foundation_finish").set_value(Finish.DEWY)
    _button(at, "Apply Filters").click().run()
    assert _cards_html(at) != before
    _button(at, "Clear Filters").click().run()
    no_errors(at)
    assert _cards_html(at) == before
    assert at.selectbox(key="bs_sf_foundation_finish").value == "Any"


def test_shade_finder_category_switch_shows_own_filters_and_drops_old_ones():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.selectbox(key="bs_sf_foundation_finish").set_value(Finish.MATTE)
    _button(at, "Apply Filters").click().run()
    at.get("button_group")[0].set_value(Category.LIPSTICK).run()
    no_errors(at)
    keys = {s.key for s in at.selectbox}
    assert {"bs_sf_lipstick_look", "bs_sf_lipstick_family", "bs_sf_lipstick_int",
            "bs_sf_lipstick_finish"} <= keys
    assert not any(k.startswith("bs_sf_foundation") for k in keys)
    assert "Apply Filters" in [b.label for b in at.button]
    at.get("button_group")[0].set_value(Category.FOUNDATION).run()
    assert at.selectbox(key="bs_sf_foundation_finish").value == "Any"


FILTER_KEYS = {
    Category.FOUNDATION: {"bs_sf_foundation_finish", "bs_sf_foundation_cov"},
    Category.CONCEALER: {"bs_sf_concealer_purpose", "bs_sf_concealer_finish"},
    Category.COLOR_CORRECTOR: {"bs_sf_color_corrector_target"},
    Category.LIPSTICK: {"bs_sf_lipstick_look", "bs_sf_lipstick_family", "bs_sf_lipstick_int",
                        "bs_sf_lipstick_finish"},
    Category.BLUSH: {"bs_sf_blush_look", "bs_sf_blush_family", "bs_sf_blush_int",
                     "bs_sf_blush_form"},
    Category.EYELINER: {"bs_sf_eyeliner_look", "bs_sf_eyeliner_family", "bs_sf_eyeliner_form"},
}


@pytest.mark.parametrize("category", list(FILTER_KEYS))
def test_shade_finder_each_category_shows_only_its_own_filters(category):
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.get("button_group")[0].set_value(category).run()
    no_errors(at)
    keys = {w.key for w in [*at.selectbox, *at.radio] if (w.key or "").startswith("bs_sf_")
            and not w.key.startswith("bs_sf_profile")}
    assert keys == FILTER_KEYS[category]
    assert {"Apply Filters", "Clear Filters"} <= {b.label for b in at.button}


def test_shade_finder_color_corrector_needs_applied_concern():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.get("button_group")[0].set_value(Category.COLOR_CORRECTOR).run()
    assert _cards(at) == 0
    at.selectbox(key="bs_sf_color_corrector_target").set_value(CorrectionTarget.REDNESS).run()
    assert _cards(at) == 0  # chosen but not applied
    at.selectbox(key="bs_sf_color_corrector_target").set_value(CorrectionTarget.REDNESS)
    _button(at, "Apply Filters").click().run()
    no_errors(at)
    assert _cards(at) > 0 and "eligible shades" in _summary(at)


def test_shade_finder_applies_several_blush_filters_together_and_clears_them_all():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.get("button_group")[0].set_value(Category.BLUSH).run()
    before = _cards_html(at)
    at.selectbox(key="bs_sf_blush_family").set_value(ColorFamily.BERRY)
    at.selectbox(key="bs_sf_blush_int").set_value(Intensity.BOLD)
    at.selectbox(key="bs_sf_blush_form").set_value(Formulation.CREAM)
    _button(at, "Apply Filters").click().run()
    no_errors(at)
    assert _cards_html(at) != before
    assert at.selectbox(key="bs_sf_blush_family").value == ColorFamily.BERRY
    assert at.selectbox(key="bs_sf_blush_form").value == Formulation.CREAM
    _button(at, "Clear Filters").click().run()
    no_errors(at)
    assert _cards_html(at) == before
    assert all(at.selectbox(key=f"bs_sf_blush_{k}").value == "Any"
               for k in ("look", "family", "int", "form"))


def test_shade_finder_applied_lipstick_colour_reorders_results():
    at = open_page("shades", **{state.PROFILE: _fresh_profile()})
    at.get("button_group")[0].set_value(Category.LIPSTICK).run()
    before = _cards_html(at)
    at.selectbox(key="bs_sf_lipstick_family").set_value(ColorFamily.RED)
    _button(at, "Apply Filters").click().run()
    no_errors(at)
    assert _cards_html(at) != before
