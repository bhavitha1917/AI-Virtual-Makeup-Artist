"""Page registry and top navigation."""

from __future__ import annotations

from functools import lru_cache

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from src.ui.components import safe_page
from src.ui.pages import about, face_analysis, home, routine, shade_finder

HOME, ANALYSIS, SHADES, ROUTINE, ABOUT = "home", "analysis", "shades", "routine", "about"


PAGE_SPECS = (
    (HOME, home.render, "Home", None),  # default page is served at "/"
    (ANALYSIS, face_analysis.render, "Face Analysis", "face-analysis"),
    (SHADES, shade_finder.render, "Shade Finder", "shade-finder"),
    (ROUTINE, routine.render, "My Makeup Routine", "routine"),
    (ABOUT, about.render, "About & Methodology", "about"),
)


@lru_cache(maxsize=len(PAGE_SPECS))
def get_pages(default: str = HOME) -> dict[str, StreamlitPage]:
    """Page objects hold no user data, so one registry per process is safe.

    ``default`` selects the landing page (Home in the app; other pages in UI tests).
    Pages are identified by ``url_path``, so links work across registries.
    """
    return {
        name: st.Page(safe_page(render), title=title, url_path=url, default=(name == default))
        for name, render, title, url in PAGE_SPECS
    }


def page(name: str) -> StreamlitPage:
    return get_pages()[name]


def build_navigation(default: str = HOME, *, visible: bool = True) -> StreamlitPage:
    """``visible=False`` registers the pages without showing the menu (welcome screen),
    so ``st.switch_page`` can still reach them."""
    return st.navigation(list(get_pages(default).values()), position="top" if visible else "hidden")
