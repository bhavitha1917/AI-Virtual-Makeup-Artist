"""Reusable presentation components. All data- or user-derived text is HTML-escaped."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from functools import wraps
from html import escape

import streamlit as st

from src.config import APP_NAME, APP_VERSION
from src.core.errors import BeautyStudioError
from src.core.features import (
    FEATURE_LABELS,
    FEATURE_NAMES,
    FEATURE_VALUES,
    FeatureEstimate,
    FeatureStatus,
    QualityCheck,
    Severity,
    UserProfile,
)
from src.recommendation.explanations import NAMES as COMPONENT_NAMES
from src.recommendation.service import Recommendation
from src.routine.routine_generator import Routine, RoutineStep

logger = logging.getLogger(__name__)

ESTIMATE_NOTICE = (
    "Skin depth, undertone, eye shape and face shape are <strong>estimates</strong> from a single "
    "photo. Lighting, camera processing and makeup all affect them. Review and correct them "
    "below — this is not a medical or scientifically validated assessment."
)
STATUS_BADGES = {
    FeatureStatus.UNKNOWN: ("Not available", "neutral"),
    FeatureStatus.UNCERTAIN: ("Uncertain", "warn"),
    FeatureStatus.ESTIMATED: ("Estimated", "info"),
    FeatureStatus.USER_CONFIRMED: ("Confirmed by you", "ok"),
}
SEVERITY_BADGES = {Severity.OK: "ok", Severity.WARNING: "warn", Severity.FAIL: "fail"}
NOT_SET = "Not set"


def e(text: object) -> str:
    return escape(str(text), quote=True)


def html(markup: str) -> None:
    st.html(markup)


def human(value: str | None) -> str:
    return (value or "").replace("_", " ")


# ------------------------------------------------------------------ text blocks
def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f'<p class="bs-lead">{e(subtitle)}</p>' if subtitle else ""
    html(f'<div class="bs-page-header"><p class="bs-eyebrow">{e(eyebrow)}</p>'
         f'<h1 class="bs-h1">{e(title)}</h1>{sub}</div>')


def section_title(title: str, kicker: str = "", subtitle: str = "") -> None:
    k = f'<p class="bs-eyebrow">{e(kicker)}</p>' if kicker else ""
    s = f'<p class="bs-muted">{e(subtitle)}</p>' if subtitle else ""
    html(f'<div class="bs-section">{k}<h2 class="bs-h2">{e(title)}</h2>{s}</div>')


def notice(message_html: str, kind: str = "info") -> None:
    """``message_html`` must be trusted markup (constants or pre-escaped text)."""
    cls = {"info": "", "warn": " bs-notice-warn", "error": " bs-notice-error"}[kind]
    role = ' role="alert"' if kind == "error" else ""
    html(f'<div class="bs-notice{cls}"{role}>{message_html}</div>')


def empty_state(title: str, body: str) -> None:
    html(f'<div class="bs-empty"><h3 class="bs-h3">{e(title)}</h3><p>{e(body)}</p></div>')


def error_card(title: str, message: str, hint: str = "") -> None:
    h = f"<br><span class='bs-small'>{e(hint)}</span>" if hint else ""
    notice(f"<strong>{e(title)}</strong><br>{e(message)}{h}", kind="error")


def badge(label: str, kind: str = "info") -> str:
    return f'<span class="bs-badge bs-badge-{kind}">{e(label)}</span>'


def chips(values: Iterable[str]) -> str:
    return "".join(f'<span class="bs-chip">{e(v)}</span>' for v in values if v)


def footer() -> None:
    html(f"""
<footer class="bs-footer">
  <div><p class="bs-footer-brand">{e(APP_NAME)}</p>
  <p>An explainable, vision-based cosmetic recommendation and routine expert system.
  Version {e(APP_VERSION)}.</p></div>
  <div><p><strong>Privacy.</strong> Photos are analysed in memory on the server running this app,
  never saved to disk, logged or sent to third parties. Results live only in your browser
  session.</p>
  <p>Estimates are not medical advice. Products shown are fictional demonstration items.</p></div>
</footer>""")


# ------------------------------------------------------------------ page boundary
def safe_page(render: Callable[[], None]) -> Callable[[], None]:
    """Catch unexpected errors at the page boundary; log without user data."""

    @wraps(render)
    def wrapper() -> None:
        try:
            render()
        except BeautyStudioError as exc:
            logger.warning("handled error on page %s: %s", render.__module__, exc.code)
            error_card("Something needs your attention", exc.user_message)
        except Exception:  # noqa: BLE001 - last-resort boundary; Streamlit control flow is BaseException
            logger.exception("unexpected error on page %s", render.__module__)
            error_card("Something went wrong",
                       "An unexpected error occurred. Please try again or reload the page.")

    return wrapper


# ------------------------------------------------------------------ analysis
def feature_value_text(est: FeatureEstimate) -> tuple[str, bool]:
    if est.usable:
        return human(est.value), True
    if est.status is FeatureStatus.UNCERTAIN and est.candidates:
        return "Between " + " and ".join(human(c) for c in est.candidates), False
    if est.status is FeatureStatus.UNCERTAIN:
        return "Could not decide", False
    return "Not available", False


def feature_cards(features: dict[str, FeatureEstimate] | UserProfile) -> None:
    feats = features.features if isinstance(features, UserProfile) else features
    cards = []
    for name in FEATURE_NAMES:
        est = feats[name]
        label, kind = STATUS_BADGES[est.status]
        text, is_value = feature_value_text(est)
        reasons = "".join(f"<p>{e(r)}</p>" for r in est.reasons[:2])
        cls = "bs-feature-value" + ("" if is_value else " bs-unset")
        cards.append(
            f'<div class="bs-feature"><div class="bs-feature-label">{e(FEATURE_LABELS[name])}'
            f'</div><div class="{cls}">{e(text)}</div>{badge(label, kind)}{reasons}</div>')
    html(f'<div class="bs-feature-grid">{"".join(cards)}</div>')


def quality_checks(checks: Sequence[QualityCheck]) -> None:
    items = "".join(
        f'<div class="bs-quality-item">{badge(c.label, SEVERITY_BADGES[c.severity])}'
        f'<div>{e(c.message)}</div></div>' for c in checks)
    html(f'<div class="bs-quality">{items}</div>')


def profile_editor(profile: UserProfile, key: str, submit_label: str = "Save profile"
                   ) -> dict[str, str | None] | None:
    """Form with one select per feature. Returns selections on submit, else ``None``."""
    with st.form(key=key, border=False):
        cols = st.columns(len(FEATURE_NAMES))
        selections: dict[str, str | None] = {}
        for col, name in zip(cols, FEATURE_NAMES, strict=True):
            est = profile.get(name)
            options = [NOT_SET, *FEATURE_VALUES[name]]
            index = options.index(est.value) if est.usable else 0
            help_text = None
            if est.status is FeatureStatus.UNCERTAIN and est.candidates:
                help_text = "The analysis was uncertain between: " + ", ".join(
                    human(c) for c in est.candidates)
            elif name == "eye_shape":
                help_text = "Monolid can be chosen here; it is never assigned automatically."
            with col:
                choice = st.selectbox(FEATURE_LABELS[name], options, index=index,
                                      format_func=lambda v: human(v).capitalize(),
                                      help=help_text, key=f"{key}_{name}")
            selections[name] = None if choice == NOT_SET else choice
        submitted = st.form_submit_button(submit_label, type="primary")
    return selections if submitted else None


def profile_summary(profile: UserProfile) -> None:
    parts = []
    for name in FEATURE_NAMES:
        est = profile.get(name)
        text, _ = feature_value_text(est)
        label, kind = STATUS_BADGES[est.status]
        parts.append(f'<span class="bs-chip"><strong>{e(FEATURE_LABELS[name])}:</strong> '
                     f'{e(text)} · {e(label)}</span>')
    html(f'<div>{"".join(parts)}</div>')


# ------------------------------------------------------------------ products
def _swatch(hex_value: str | None) -> str:
    if hex_value:
        return (f'<div class="bs-product-swatch" style="background:{e(hex_value)}" '
                f'role="img" aria-label="Illustrative swatch"></div>')
    return '<div class="bs-product-swatch bs-none" role="img" aria-label="No swatch"></div>'


def product_card(rec: Recommendation) -> None:
    p, s = rec.product, rec.shade
    finish = s.finish or p.finish
    meta = chips([
        f"Finish: {human(finish.value)}" if finish else "",
        f"Coverage: {human(p.coverage.value)}" if p.coverage else "",
        f"Formula: {human(p.formulation.value)}" if p.formulation else "",
        f"Price: {p.price:.2f} {p.currency}" if p.price is not None and p.currency else "",
    ])
    status_kind = {"Strong fit": "ok", "Good fit": "info", "Partial fit": "neutral"}[rec.label]
    provenance = badge("Demo product", "neutral") if s.verification_status.value == "demo" else \
        badge("Verified data", "ok") if s.verification_status.value == "verified" else \
        badge("Unverified data", "warn")
    reasons = "".join(f"<li>{e(r)}</li>" for r in rec.reasons)
    caveats = "".join(f"<p>{e(c)}</p>" for c in rec.caveats)
    html(f"""
<div class="bs-product">
  <div class="bs-product-head">{_swatch(s.illustrative_swatch_hex)}
    <div><div class="bs-product-brand">{e(p.brand)}</div>
    <div class="bs-product-name">{e(p.product_name)}</div>
    <div class="bs-product-shade">Shade: {e(s.shade_name)}</div></div></div>
  <div>{meta}</div>
  <div class="bs-product-fit">{badge(rec.label, status_kind)}
    <span class="bs-small">Fit score {rec.score:.2f} — a ranking score, not a probability</span>
    {provenance}</div>
  <ul>{reasons}</ul>
  <div class="bs-caveats">{caveats}</div>
</div>""")


def score_breakdown(rec: Recommendation) -> None:
    rows = [{"Criterion": COMPONENT_NAMES[c.name].capitalize(), "Weight": c.weight,
             "Score": c.score, "Contribution": round(c.contribution, 3),
             "Result": human(c.outcome)} for c in rec.components]
    st.dataframe(rows, hide_index=True, width="stretch")
    if rec.unset_preferences:
        st.caption("No preference set for: " + ", ".join(rec.unset_preferences)
                   + " — these did not change the ranking.")


# ------------------------------------------------------------------ routine
def routine_step_card(step: RoutineStep) -> None:
    optional = badge("Optional", "warn") if step.optional else ""
    source = badge("Your own product", "neutral") if step.item.source == "custom" else ""
    sections = [f"<p>{e(step.purpose)}</p>",
                '<div class="bs-label">How to apply</div>', f"<p>{e(step.technique)}</p>"]
    if step.technique_note:
        sections.append(f'<p class="bs-small">{e(step.technique_note)}</p>')
    if step.instructions:
        sections.append("<ul>" + "".join(f"<li>{e(i)}</li>" for i in step.instructions) + "</ul>")
    if step.feature_tips:
        sections.append('<div class="bs-label">For your features</div><ul>'
                        + "".join(f"<li>{e(t)}</li>" for t in step.feature_tips) + "</ul>")
    if step.compatibility_notes:
        sections.append('<div class="bs-label">Compatibility</div><ul>'
                        + "".join(f"<li>{e(n)}</li>" for n in step.compatibility_notes)
                        + "</ul>")
    if step.cautions:
        sections.append('<div class="bs-label">Caution</div><ul>'
                        + "".join(f"<li>{e(c)}</li>" for c in step.cautions) + "</ul>")
    if step.optional_reason:
        sections.append(f'<p class="bs-small">{e(step.optional_reason)}</p>')
    if step.alternatives:
        sections.append('<p class="bs-small">Also in your collection: '
                        + e(", ".join(a.display_name for a in step.alternatives)) + "</p>")
    html(f"""
<div class="bs-routine-step">
  <div class="bs-routine-num" aria-label="Step {step.number}">{step.number}</div>
  <div><div class="bs-routine-title"><h3 class="bs-h3">{e(step.title)}</h3>{optional}{source}</div>
  <div class="bs-routine-product">{e(step.item.display_name)}</div>{"".join(sections)}</div>
</div>""")


def routine_view(routine: Routine) -> None:
    section_title(f"Your {routine.look_label.lower()} routine",
                  kicker=f"{len(routine.steps)} steps",
                  subtitle="Built only from the products in your collection, in a "
                           "dependency-checked order.")
    for step in routine.steps:
        routine_step_card(step)
    if routine.skipped:
        notice("<strong>Skipped:</strong> " + e("; ".join(
            f"{s.title} — {s.reason}" for s in routine.skipped)))
    for note in routine.notes:
        notice(e(note))
    if routine.suggestions:
        notice("<strong>Optional suggestions</strong> (not part of your routine):<ul>"
               + "".join(f"<li>{e(s)}</li>" for s in routine.suggestions) + "</ul>")
    if routine.general_cautions:
        notice("<strong>Good practice</strong><ul>"
               + "".join(f"<li>{e(c)}</li>" for c in routine.general_cautions) + "</ul>")
