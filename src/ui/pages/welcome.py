"""Welcome screen shown once per browser session, before the main navigation."""

from __future__ import annotations

import base64
import logging
from functools import lru_cache

import streamlit as st

from src.config import ASSETS_DIR
from src.ui import navigation as nav
from src.ui import state
from src.ui.components import html

logger = logging.getLogger(__name__)

BACKGROUND_IMAGE = ASSETS_DIR / "welcome_beauty_studio.png"


@lru_cache(maxsize=1)
def background_css() -> str:
    """The photo as the app background while the welcome screen is shown (sizing, overlay and
    layout live in ``assets/styles.css``).

    Inlined as a data URI because Streamlit does not serve arbitrary repository files; this
    keeps the same repo-relative path working locally and when deployed. Set as a plain
    property: browsers cap custom-property values (~2 MB in Chromium), which this exceeds.
    Read once per process.
    """
    try:
        data = BACKGROUND_IMAGE.read_bytes()
    except OSError:
        logger.warning("Welcome background image not found; showing the plain welcome screen.")
        return ""
    encoded = base64.b64encode(data).decode("ascii")
    return (".stApp:has(.st-key-bs-welcome) "
            f"{{ background-image: url(data:image/png;base64,{encoded}); }}")


def render() -> None:
    css = background_css()
    if css:
        html(f"<style>{css}</style>")
    with st.container(key="bs-welcome"):
        html("""<h1 class="bs-welcome-brand"><span class="bs-welcome-the">The</span>
<span>Beauty</span> <span>Studio</span></h1>
<div class="bs-welcome-divider" aria-hidden="true"><span></span><i></i><span></span></div>
<p class="bs-welcome-tagline">Your Face, Your Shades, Your Beauty.</p>""")
        if st.button("Get Started →", type="primary", key="bs_enter"):
            state.enter_studio(st.session_state)
            st.switch_page(nav.page(nav.HOME))
