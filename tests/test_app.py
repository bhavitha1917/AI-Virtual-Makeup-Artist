"""Streamlit AppTest smoke tests for every page and key interactions."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from src.core.enums import Category
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
