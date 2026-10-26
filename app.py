"""The Beauty Studio — Streamlit entry point.

Run with:  streamlit run app.py
All logic lives in ``src/``; this file only configures the page and starts navigation.
"""

from __future__ import annotations

import streamlit as st

from src.config import APP_NAME
from src.logging_config import configure_logging
from src.ui.components import footer
from src.ui.navigation import build_navigation
from src.ui.pages import welcome
from src.ui.state import has_entered, init_state
from src.ui.theme import inject_theme

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="collapsed")
configure_logging()
inject_theme()
init_state(st.session_state)
if has_entered(st.session_state):
    build_navigation().run()
    footer()
else:
    build_navigation(visible=False)
    welcome.render()
