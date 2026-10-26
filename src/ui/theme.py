"""Shared stylesheet injection. Colours/fonts for native widgets come from
``.streamlit/config.toml``; ``assets/styles.css`` styles the custom components."""

from __future__ import annotations

from functools import lru_cache

import streamlit as st

from src.config import ASSETS_DIR


@lru_cache(maxsize=1)
def _stylesheet() -> str:
    return (ASSETS_DIR / "styles.css").read_text(encoding="utf-8")


def inject_theme() -> None:
    st.html(f"<style>{_stylesheet()}</style>")
