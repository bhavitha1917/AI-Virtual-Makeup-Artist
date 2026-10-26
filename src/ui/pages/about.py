"""About & Methodology page."""

from __future__ import annotations

import streamlit as st

from src.config import APP_VERSION
from src.recommendation.ranking import WEIGHTS
from src.ui.components import html, page_header, section_title


def render() -> None:
    page_header("About & methodology", "How The Beauty Studio works",
                "A concise overview of the engineering decisions, for curious users and "
                "project evaluators.")

    html("""
<div class="bs-trust">
  <div class="bs-card"><div class="bs-kicker">Overview</div><h3 class="bs-h3">Two workflows</h3>
  <p class="bs-muted">Discover My Shades (photo → estimates → ranked shades) and Create My
  Routine (your products + a look → ordered steps). Either works on its own.</p></div>
  <div class="bs-card"><div class="bs-kicker">Architecture</div><h3 class="bs-h3">Layered and
  local</h3><p class="bs-muted">Streamlit UI → vision, recommendation and routine services →
  validated JSON knowledge base. No database, no paid APIs, no language model.</p></div>
  <div class="bs-card"><div class="bs-kicker">Status</div><h3 class="bs-h3">Version """
         + APP_VERSION + """</h3><p class="bs-muted">Release 1.0 scope. Heuristics are
  provisional and have not been validated on a labelled dataset.</p></div>
</div>""")

    section_title("Vision pipeline", kicker="Analyze")
    html("""<div class="bs-card"><ul>
<li><strong>Validation:</strong> format detected from content (JPEG, PNG, WebP), ≤ 10 MB,
≤ 40 MP, shorter side ≥ 256 px, EXIF orientation applied.</li>
<li><strong>Landmarks:</strong> MediaPipe Face Landmarker (478 points); exactly one face
required; landmarks validated before use.</li>
<li><strong>Quality checks:</strong> sharpness, exposure, clipped highlights/shadows, lighting
balance between cheeks, face size, head yaw and roll, open eyes.</li>
<li><strong>Skin:</strong> cheek and forehead samples, excluding eyes, brows and lips; trimmed of
highlights and shadows; converted to CIELAB. Depth uses the Individual Typology Angle;
a possible undertone uses the Lab hue angle. Obstructed regions are dropped; K-Means is used
only as a consistency check.</li>
<li><strong>Geometry:</strong> face shape from several normalized ratios and the chin angle; eye
shape from openings at three points, taper and brow-to-lid space, plus roll-corrected tilt.</li>
<li><strong>Honest outputs:</strong> each feature is unknown, uncertain (with candidates),
estimated, or confirmed by you. No confidence percentages are produced.</li>
</ul></div>""")

    section_title("Product matching", kicker="Personalize")
    rows = [{"Category": c.value.replace("_", " ").capitalize(),
             "Weighted criteria": ", ".join(f"{k.replace('_', ' ')} {w:.2f}"
                                            for k, w in weights.items())}
            for c, weights in WEIGHTS.items()]
    st.dataframe(rows, hide_index=True, width="stretch")
    html("""<div class="bs-notice">Hard compatibility filters (for example, a foundation more than
one depth level away or with the opposite undertone) are applied <strong>before</strong>
scoring and are never relaxed silently. Missing product metadata scores zero rather than being
rewarded. The fit score ranks catalog items; it is not a probability of a perfect match.</div>""")

    section_title("Routine expert system", kicker="Apply")
    html("""<div class="bs-card"><ul>
<li>Sixteen step definitions with techniques per formulation, written as general cosmetic
guidance.</li>
<li>Look, preference and feature rules; within a rule group the highest priority wins, and
equal-priority overlapping rules are rejected as contradictory when the data loads.</li>
<li>Conditional ordering constraints (for example cream blush before powder, powder blush after;
eyes first for Glam) are sorted with a dependency graph; every possible context is checked for
cycles at load time.</li>
<li>Only products in your collection become steps. Suggestions for products you do not own are
listed separately and marked optional.</li>
</ul></div>""")

    section_title("Testing, limitations and privacy", kicker="Quality")
    html("""
<div class="bs-trust">
  <div class="bs-card"><h3 class="bs-h3">Testing</h3><p class="bs-muted">Automated pytest suite
  with synthetic images and landmark sets, fictional test catalogs, rule-validation tests and
  Streamlit page smoke tests, plus manual browser checks. See docs/TEST_PLAN.md.</p></div>
  <div class="bs-card"><h3 class="bs-h3">Limitations</h3><p class="bs-muted">Uncalibrated photos;
  unvalidated thresholds; olive undertones and monolids are not detected automatically; the
  catalog is fictional demonstration data. See docs/limitations.md.</p></div>
  <div class="bs-card"><h3 class="bs-h3">Privacy</h3><p class="bs-muted">No accounts, no
  analytics, no identity recognition. Photos are processed in memory and never written to disk
  or logs; results are kept only in your session.</p></div>
</div>""")
