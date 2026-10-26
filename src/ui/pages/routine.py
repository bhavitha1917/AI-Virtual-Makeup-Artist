"""My Makeup Routine page: inventory management, look selection, routine generation."""

from __future__ import annotations

import streamlit as st

from src.core.enums import (
    CATEGORY_LABELS,
    Category,
    ConcealerOrder,
    Coverage,
    Finish,
    Formulation,
    Intensity,
    Look,
)
from src.core.errors import CatalogError, RoutineError
from src.core.features import EYE_SHAPE, EYE_TILT, FACE_SHAPE, FEATURE_LABELS
from src.data.schema import Catalog
from src.routine.inventory import (
    InventoryItem,
    add_item,
    create_custom_item,
    item_from_catalog,
    remove_item,
    update_item,
)
from src.routine.routine_generator import (
    RoutinePreferences,
    RoutineRequest,
    generate_routine,
    request_signature,
)
from src.ui import navigation as nav
from src.ui import state
from src.ui.components import (
    badge,
    e,
    empty_state,
    error_card,
    html,
    human,
    notice,
    page_header,
    routine_view,
    section_title,
)
from src.ui.resources import get_catalog, get_rules

NOT_SURE = "Not sure"
CATEGORIES = list(Category)


def _fmt_enum(v) -> str:
    return v if isinstance(v, str) else human(v.value).capitalize()


def _optional(choice):
    return None if isinstance(choice, str) else choice


def _add_from_catalog(ss, catalog: Catalog) -> None:
    category = st.selectbox("Category", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c],
                            key="bs_cat_category")
    products = catalog.products_in(category)
    if not products:
        st.caption("The catalog has no products in this category yet — add it as your own "
                   "product instead.")
        return
    product = st.selectbox("Product", products, format_func=lambda p: p.display_name,
                           key=f"bs_cat_product_{category.value}")
    shade = None
    shades = catalog.shades_for(product)
    if shades:
        shade = st.selectbox("Shade", shades, format_func=lambda s: s.shade_name,
                             key=f"bs_cat_shade_{product.product_id}")
    if st.button("Add to my products", type="primary", key="bs_cat_add"):
        try:
            state.set_inventory(ss, add_item(state.get_inventory(ss),
                                             item_from_catalog(product, shade)))
            state.flash(ss, f"Added {product.display_name}.")
            st.rerun()
        except RoutineError as exc:
            st.error(exc.user_message)


def _add_custom(ss) -> None:
    with st.form("bs_custom_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox("Category", CATEGORIES, key="bs_custom_category",
                                    format_func=lambda c: CATEGORY_LABELS[c])
            brand = st.text_input("Brand (optional)", max_chars=60, key="bs_custom_brand")
            formulation = st.selectbox("Formula (optional)", [NOT_SURE, *Formulation],
                                       format_func=_fmt_enum)
        with c2:
            name = st.text_input("Product name", max_chars=80, key="bs_custom_name")
            shade = st.text_input("Shade (optional)", max_chars=60)
            finish = st.selectbox("Finish (optional)", [NOT_SURE, *Finish], format_func=_fmt_enum)
        submitted = st.form_submit_button("Add my product", type="primary")
    if submitted:
        try:
            item = create_custom_item(category=category, product_name=name, brand=brand,
                                      shade_name=shade, formulation=_optional(formulation),
                                      finish=_optional(finish))
            state.set_inventory(ss, add_item(state.get_inventory(ss), item))
            state.flash(ss, f"Added {item.display_name}.")
            st.rerun()
        except RoutineError as exc:
            st.error(exc.user_message)


def _edit_item(ss, item: InventoryItem, catalog: Catalog) -> None:
    with st.popover("Edit", width="content"):
        if item.source == "custom":
            with st.form(f"bs_edit_{item.item_id}", border=False):
                name = st.text_input("Product name", item.product_name, max_chars=80)
                brand = st.text_input("Brand", item.brand, max_chars=60)
                shade = st.text_input("Shade", item.shade_name or "", max_chars=60)
                forms = [NOT_SURE, *Formulation]
                formulation = st.selectbox(
                    "Formula", forms, format_func=_fmt_enum,
                    index=forms.index(item.formulation) if item.formulation else 0)
                if st.form_submit_button("Save changes", type="primary"):
                    try:
                        state.set_inventory(ss, update_item(
                            state.get_inventory(ss), item.item_id, product_name=name,
                            brand=brand, shade_name=shade, formulation=_optional(formulation)))
                        st.rerun()
                    except RoutineError as exc:
                        st.error(exc.user_message)
            return
        product = catalog.products.get(item.catalog_product_id or "")
        shades = catalog.shades_for(product) if product else []
        if not shades:
            st.caption("This catalog product has no shades to change. Remove it and add another "
                       "product instead.")
            return
        ids = [s.shade_id for s in shades]
        shade = st.selectbox("Shade", shades, format_func=lambda s: s.shade_name,
                             index=ids.index(item.catalog_shade_id)
                             if item.catalog_shade_id in ids else 0,
                             key=f"bs_edit_shade_{item.item_id}")
        if st.button("Save shade", type="primary", key=f"bs_edit_save_{item.item_id}"):
            try:
                state.set_inventory(ss, update_item(
                    state.get_inventory(ss), item.item_id, shade_name=shade.shade_name,
                    catalog_shade_id=shade.shade_id, finish=shade.finish or product.finish))
                st.rerun()
            except RoutineError as exc:
                st.error(exc.user_message)


def _inventory_list(ss, catalog: Catalog) -> None:
    inventory = state.get_inventory(ss)
    if not inventory:
        empty_state("Your collection is empty",
                    "Add the products you own — from the catalog or as your own entries. You "
                    "don't need every category; the routine adapts to what you have.")
        return
    order = {c: i for i, c in enumerate(CATEGORIES)}
    for item in sorted(inventory, key=lambda i: order[i.category]):
        c1, c2, c3 = st.columns([5, 1.1, 1.3], vertical_alignment="center")
        with c1:
            source = badge("Catalog" if item.source == "catalog" else "Own product",
                           "info" if item.source == "catalog" else "neutral")
            details = " · ".join(x for x in (
                CATEGORY_LABELS[item.category],
                f"formula: {human(item.formulation.value)}" if item.formulation else "",
            ) if x)
            html(f'<div class="bs-inventory-item">{e(item.display_name)} {source}'
                 f'<span class="bs-small">{e(details)}</span></div>')
        with c2:
            _edit_item(ss, item, catalog)
        with c3:
            if st.button("Remove", key=f"bs_rm_{item.item_id}"):
                state.set_inventory(ss, remove_item(state.get_inventory(ss), item.item_id))
                st.rerun()


def _preferences(rules) -> tuple[Look, RoutinePreferences]:
    look = st.segmented_control("Look", list(Look), default=Look.EVERYDAY, required=True,
                                format_func=lambda lk: rules.looks[lk]["label"],
                                key="bs_rt_look") or Look.EVERYDAY
    st.caption(rules.looks[look]["description"])
    c1, c2 = st.columns(2)
    with c1:
        coverage = st.selectbox("Coverage preference", ["No preference", Coverage.LIGHT,
                                                        Coverage.FULL],
                                format_func=_fmt_enum, key="bs_rt_cov")
    with c2:
        intensity = st.selectbox("Colour intensity", ["No preference", Intensity.SOFT,
                                                      Intensity.BOLD],
                                 format_func=_fmt_enum, key="bs_rt_int")
    order = st.radio("Concealer", list(ConcealerOrder), horizontal=True, key="bs_rt_order",
                     format_func=lambda o: {"after_foundation": "After foundation",
                                            "before_foundation": "Before foundation"}[o.value])
    return look, RoutinePreferences(coverage=_optional(coverage), intensity=_optional(intensity),
                                    concealer_order=order)


def render() -> None:
    ss = st.session_state
    page_header("Workflow two · Create my routine", "My Makeup Routine",
                "Your products, your look — a numbered routine with technique for each step.")
    if msg := state.flash(ss):
        st.success(msg)
    try:
        catalog, rules = get_catalog(), get_rules()
    except CatalogError as exc:
        error_card("The knowledge base could not be loaded", exc.user_message,
                   "Run `python scripts/validate_data.py` for details.")
        return

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        section_title("My products", kicker="Step 1")
        with st.container(key="bs-card-add"):
            tab_catalog, tab_custom = st.tabs(["From the catalog", "My own product"])
            with tab_catalog:
                _add_from_catalog(ss, catalog)
            with tab_custom:
                _add_custom(ss)
        _inventory_list(ss, catalog)
        if state.get_inventory(ss) and st.button("Remove all products", key="bs_rm_all"):
            state.set_inventory(ss, ())
            state.clear_routine(ss)
            st.rerun()

    with right:
        section_title("Look and preferences", kicker="Step 2")
        with st.container(key="bs-card-prefs"):
            look, prefs = _preferences(rules)
            profile = state.get_profile(ss)
            usable = [FEATURE_LABELS[n] + ": " + human(profile.get(n).value)
                      for n in (FACE_SHAPE, EYE_SHAPE, EYE_TILT) if profile.get(n).usable]
            if usable:
                st.caption("Feature tips will use — " + "; ".join(usable))
            else:
                st.caption("No face or eye shape set, so feature-specific tips are not included.")
                st.page_link(nav.page(nav.ANALYSIS), label="Add my features")
            generate = st.button("Generate my routine", type="primary", width="stretch",
                                 disabled=not state.get_inventory(ss))

    request = RoutineRequest(inventory=state.get_inventory(ss), look=look, preferences=prefs,
                             features=dict(state.get_profile(ss).features))
    signature = request_signature(request)
    if generate:
        try:
            with st.spinner("Building your routine…"):
                state.store_routine(ss, generate_routine(request, rules))
        except RoutineError as exc:
            state.clear_routine(ss)
            error_card("We couldn't build a routine", exc.user_message)

    routine = state.current_routine(ss, signature)
    if routine is not None:
        routine_view(routine)
        if st.button("Clear this routine", key="bs_rt_clear"):
            state.clear_routine(ss)
            st.rerun()
    elif state.routine_is_stale(ss, signature):
        notice("Your products, look or preferences changed since the routine was generated. "
               "Select <strong>Generate my routine</strong> to update it.", kind="warn")
    elif state.get_inventory(ss):
        notice("Choose a look and select <strong>Generate my routine</strong>.")
