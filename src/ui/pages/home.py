"""Home page."""

from __future__ import annotations

import streamlit as st

from src.ui import navigation as nav
from src.ui.components import html, section_title

# Illustrative palette dots (decorative; not product colours).
HERO_SWATCHES = ("#F3D9CC", "#E6C3AE", "#CFA084", "#A9785A", "#7A5039", "#4F3324")
ACCENT_SWATCHES = ("#D88E95", "#C9828E", "#A9605F", "#8F6579", "#6E1F3A", "#3E2A22")


def _dots(colors: tuple[str, ...]) -> str:
    return "".join(f'<span class="bs-swatch-dot" style="background:{c}"></span>' for c in colors)


def render() -> None:
    html(f"""
<section class="bs-hero">
  <div>
    <p class="bs-eyebrow">The Beauty Studio</p>
    <h1 class="bs-h1">Your Face. Your Shades. Your Beauty.</h1>
    <p class="bs-lead">A private, explainable makeup consultation. Estimate your complexion and
    features from a photo, explore shades ranked with clear reasons, and get a step-by-step
    routine built only from the products you already own.</p>
  </div>
  <div class="bs-hero-art" aria-hidden="true">
    <div class="bs-kicker">Complexion depths</div>
    <div class="bs-swatch-row">{_dots(HERO_SWATCHES)}</div>
    <div class="bs-kicker">Colour stories</div>
    <div class="bs-swatch-row">{_dots(ACCENT_SWATCHES)}</div>
    <p class="bs-hero-caption">Illustrative colours only.</p>
  </div>
</section>""")

    col_a, col_b = st.columns(2, gap="medium")
    with col_a, st.container(key="bs-card-home-shades"):
        html("""<div class="bs-feature-card"><div class="bs-kicker">Workflow one</div>
<h3 class="bs-h2">Discover My Shades</h3>
<p class="bs-muted">Upload or take a photo. We check its quality, estimate skin depth, a possible
undertone, eye and face shape, and let you correct anything before ranking foundation,
concealer, corrector, lipstick, blush and eyeliner shades.</p></div>""")
        if st.button("Discover My Shades", type="primary", key="cta_shades"):
            st.switch_page(nav.page(nav.ANALYSIS))
    with col_b, st.container(key="bs-card-home-routine"):
        html("""<div class="bs-feature-card"><div class="bs-kicker">Workflow two</div>
<h3 class="bs-h2">Create My Routine</h3>
<p class="bs-muted">Tell us what is in your makeup bag — from our catalog or your own entries —
choose Everyday, Office, Festive or Glam, and receive a numbered routine with technique for each
product you own.</p></div>""")
        if st.button("Create My Routine", type="primary", key="cta_routine"):
            st.switch_page(nav.page(nav.ROUTINE))

    section_title("How it works", kicker="Three steps")
    html("""
<div class="bs-steps">
  <div class="bs-card"><div class="bs-step-num">1</div><h3 class="bs-h3">Analyze</h3>
  <p class="bs-muted">Facial landmarks and quality checks decide what can be measured reliably.
  Unclear results are reported as uncertain, never guessed.</p></div>
  <div class="bs-card"><div class="bs-step-num">2</div><h3 class="bs-h3">Personalize</h3>
  <p class="bs-muted">Confirm or correct each estimate, then set your preferences for finish,
  coverage, colour and intensity.</p></div>
  <div class="bs-card"><div class="bs-step-num">3</div><h3 class="bs-h3">Apply</h3>
  <p class="bs-muted">Follow ranked shade suggestions with reasons, and a routine ordered by
  explicit application rules.</p></div>
</div>""")

    section_title("Built to be trustworthy", kicker="Our approach")
    html("""
<div class="bs-trust">
  <div class="bs-card"><h3 class="bs-h3">Transparent</h3><p class="bs-muted">Every
  recommendation lists the criteria that produced it, with a full score breakdown.</p></div>
  <div class="bs-card"><h3 class="bs-h3">Private</h3><p class="bs-muted">Photos are processed in
  memory, never stored or shared. No account is needed.</p></div>
  <div class="bs-card"><h3 class="bs-h3">Honest</h3><p class="bs-muted">Photo-based colour is an
  estimate. We say when a result is uncertain and always ask you to test foundation in
  daylight.</p></div>
</div>""")
    st.page_link(nav.page(nav.ABOUT), label="Read about the methodology")
