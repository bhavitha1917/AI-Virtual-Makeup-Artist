"""Shade Finder page: profile, category filters, ranked and explained results."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

import streamlit as st

from src.core.enums import (
    CATEGORY_LABELS,
    RECOMMENDABLE_CATEGORIES,
    Category,
    ColorFamily,
    ConcealerPurpose,
    CorrectionTarget,
    Coverage,
    Finish,
    Formulation,
    Intensity,
    Look,
)
from src.core.errors import CatalogError
from src.core.features import EYE_SHAPE, EYE_TILT
from src.data.schema import Catalog
from src.recommendation.explanations import FOUNDATION_DISCLAIMER
from src.recommendation.preferences import RecommendationPreferences
from src.recommendation.service import recommend
from src.routine.rule_engine import feature_tips
from src.ui import navigation as nav
from src.ui import state
from src.ui.components import (
    e,
    empty_state,
    error_card,
    human,
    notice,
    page_header,
    product_card,
    profile_editor,
    profile_summary,
    score_breakdown,
)
from src.ui.resources import get_catalog, get_rules

ANY = "Any"
CORRECTION_LABELS = {CorrectionTarget.DARK_CIRCLES: "Under-eye darkness",
                     CorrectionTarget.REDNESS: "Redness",
                     CorrectionTarget.DULLNESS: "Dullness / sallowness"}


def _select(label: str, options: Sequence[Enum], key: str, any_label: str = ANY,
            fmt=None) -> Enum | None:
    # The enums are StrEnums, so "is it a str?" cannot tell them from the placeholder label.
    choice = st.selectbox(label, [any_label, *options], key=key,
                          format_func=lambda v: (fmt(v) if fmt else human(v.value).capitalize())
                          if isinstance(v, Enum) else v)
    return choice if isinstance(choice, Enum) else None


def _families(catalog: Catalog, category: Category) -> list[ColorFamily]:
    """Colour-family options come from the catalog itself, never invented."""
    found = {s.color_family for p in catalog.products_in(category)
             for s in catalog.shades_for(p) if s.color_family}
    return sorted(found, key=lambda f: list(ColorFamily).index(f))


def _formulations(catalog: Catalog, category: Category) -> list[Formulation]:
    found = {p.formulation for p in catalog.products_in(category) if p.formulation}
    return sorted(found, key=lambda f: list(Formulation).index(f))


def _filters(category: Category, catalog: Catalog) -> RecommendationPreferences:
    k = f"bs_sf_{category.value}"
    if category is Category.FOUNDATION:
        c1, c2 = st.columns(2)
        with c1:
            finish = _select("Finish", [Finish.MATTE, Finish.NATURAL, Finish.SATIN, Finish.DEWY],
                             f"{k}_finish")
        with c2:
            coverage = _select("Coverage", list(Coverage), f"{k}_cov")
        return RecommendationPreferences(finish=finish, coverage=coverage)
    if category is Category.CONCEALER:
        c1, c2 = st.columns(2)
        with c1:
            purpose = st.radio("Purpose", list(ConcealerPurpose), key=f"{k}_purpose",
                               horizontal=True,
                               format_func=lambda p: {"brightening": "Under-eye brightening",
                                                      "spot": "Spot concealing"}[p.value])
        with c2:
            finish = _select("Finish", [Finish.MATTE, Finish.NATURAL, Finish.RADIANT],
                             f"{k}_finish")
        return RecommendationPreferences(concealer_purpose=purpose, finish=finish)
    if category is Category.COLOR_CORRECTOR:
        target = _select("What would you like to correct?", list(CorrectionTarget),
                         f"{k}_target", any_label="Choose a concern",
                         fmt=lambda t: CORRECTION_LABELS[t])
        return RecommendationPreferences(correction_target=target)
    if category is Category.EYELINER:  # ranked by look, colour and liner type only
        c1, c2, c3 = st.columns(3)
        with c1:
            look = _select("Look", list(Look), f"{k}_look")
        with c2:
            family = _select("Colour", _families(catalog, category), f"{k}_family")
        with c3:
            form = _select("Liner type", _formulations(catalog, category), f"{k}_form")
        return RecommendationPreferences(look=look, color_family=family, formulation=form)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        look = _select("Look", list(Look), f"{k}_look")
    with c2:
        family = _select("Colour family", _families(catalog, category), f"{k}_family")
    with c3:
        intensity = _select("Intensity", list(Intensity), f"{k}_int")
    with c4:
        if category is Category.LIPSTICK:
            finish = _select("Finish", [Finish.MATTE, Finish.SATIN, Finish.GLOSS], f"{k}_finish")
            return RecommendationPreferences(look=look, color_family=family, intensity=intensity,
                                             finish=finish)
        form = _select("Formula", _formulations(catalog, category), f"{k}_form")
    return RecommendationPreferences(look=look, color_family=family, intensity=intensity,
                                     formulation=form)


def _clear_filters(category: Category) -> None:
    """Form callback: drop this category's widget state so every control returns to its default."""
    prefix = f"bs_sf_{category.value}_"
    for key in [k for k in st.session_state if isinstance(k, str) and k.startswith(prefix)]:
        del st.session_state[key]


def _filter_form(category: Category, catalog: Catalog) -> RecommendationPreferences:
    """Filters sit in a form, so selections only take effect when Apply Filters is pressed.

    Inside a form, widgets report their last *submitted* values, which makes the returned
    preferences the applied ones. The form is keyed by category, so switching category never
    carries another category's selections over.
    """
    with st.form(f"bs_sf_form_{category.value}", border=False):
        st.caption("Choose any combination, then press **Apply Filters** to update the results.")
        prefs = _filters(category, catalog)
        apply_col, clear_col = st.columns(2)
        with apply_col:
            st.form_submit_button("Apply Filters", type="primary", width="stretch")
        with clear_col:
            st.form_submit_button("Clear Filters", width="stretch",
                                  on_click=_clear_filters, args=(category,))
    return prefs


def _eyeliner_technique(profile) -> None:
    usable = {n: profile.get(n).value for n in (EYE_SHAPE, EYE_TILT) if profile.get(n).usable}
    tips = feature_tips("eyeliner", usable, get_rules()) if usable else []
    if tips:
        notice("<strong>Technique for your eyes</strong><ul>"
               + "".join(f"<li>{e(t)}</li>" for t in tips) + "</ul>")
    else:
        notice("Set your eye shape (on Face Analysis or in your profile above) to see eyeliner "
               "technique tailored to it.")


def render() -> None:
    ss = st.session_state
    page_header("Workflow one · Discover my shades", "Shade Finder",
                "Shades from the catalog ranked against your profile, with the reasons for each.")
    try:
        catalog = get_catalog()
    except CatalogError as exc:
        error_card("The product catalog could not be loaded", exc.user_message,
                   "Run `python scripts/validate_data.py` for details.")
        return
    if catalog.is_demo:
        notice("<strong>Demonstration catalog.</strong> " + e(catalog.notice))

    profile = state.get_profile(ss)
    with st.container(key="bs-card-profile"):
        st.markdown("**Your profile**")
        profile_summary(profile)
        if profile.is_empty:
            st.caption("No profile yet. Analyse a photo or set your features below.")
        with st.expander("Edit my profile", expanded=profile.is_empty):
            selections = profile_editor(profile, key="bs_sf_profile")
            if selections is not None:
                state.confirm_features(ss, selections)
                st.rerun()
        if profile.is_empty:
            st.page_link(nav.page(nav.ANALYSIS), label="Or analyse a photo instead")

    category = st.segmented_control(
        "Product category", list(RECOMMENDABLE_CATEGORIES), default=Category.FOUNDATION,
        format_func=lambda c: CATEGORY_LABELS[c], key="bs_sf_category", required=True)
    category = category or Category.FOUNDATION
    prefs = _filter_form(category, catalog)

    if category in (Category.FOUNDATION, Category.CONCEALER):
        notice("<strong>Shade verification.</strong> " + e(FOUNDATION_DISCLAIMER), kind="warn")
    if category is Category.EYELINER:
        _eyeliner_technique(profile)

    result = recommend(category, profile, prefs, catalog)
    if result.status == "needs_input":
        empty_state("A little more information needed", result.message)
        return
    if result.status == "empty":
        empty_state("No suitable verified match", result.message)
        if result.suggestions:
            notice("<ul>" + "".join(f"<li>{e(s)}</li>" for s in result.suggestions) + "</ul>")
        return

    st.caption(result.message)
    per_row = 3
    for start in range(0, len(result.items), per_row):
        cols = st.columns(per_row, gap="medium")
        for col, rec in zip(cols, result.items[start:start + per_row], strict=False):
            with col:
                product_card(rec)
                with st.expander("Score breakdown"):
                    score_breakdown(rec)
