import pytest

from src.core.enums import Category, ConcealerOrder, Coverage, Formulation, Look
from src.core.errors import RoutineError
from src.core.features import EYE_SHAPE, FACE_SHAPE, FeatureEstimate, FeatureStatus
from src.routine.inventory import (
    add_item,
    create_custom_item,
    item_from_catalog,
    remove_item,
    update_item,
)
from src.routine.routine_generator import (
    UNKNOWN_FORMULATION_NOTE,
    RoutinePreferences,
    RoutineRequest,
    generate_routine,
    request_signature,
)


def custom(category, name=None, formulation=None):
    return create_custom_item(category=category, product_name=name or f"My {category}",
                              formulation=formulation)


def order(routine):
    return [s.step_id for s in routine.steps]


def full_inventory():
    return (
        custom("skin_prep", formulation="cream"),
        custom("primer", formulation="liquid"),
        custom("color_corrector", formulation="cream"),
        custom("foundation", formulation="liquid"),
        custom("concealer", formulation="liquid"),
        custom("powder", formulation="powder"),
        custom("blush", formulation="powder"),
        custom("eyeshadow", formulation="powder"),
        custom("eyeliner", formulation="pencil"),
        custom("mascara", formulation="liquid"),
        custom("lip_liner", formulation="pencil"),
        custom("lipstick", formulation="stick"),
        custom("setting_spray", formulation="spray"),
    )


def gen(inventory, look="everyday", rules=None, **kw):
    return generate_routine(RoutineRequest(tuple(inventory), look, **kw), rules)


# ----------------------------------------------------------------- inventory
def test_custom_item_validation():
    with pytest.raises(RoutineError):
        create_custom_item(category="foundation", product_name="   ")
    with pytest.raises(RoutineError):
        create_custom_item(category="perfume", product_name="X")
    with pytest.raises(RoutineError):
        create_custom_item(category="foundation", product_name="x" * 200)
    item = create_custom_item(category="foundation", product_name="  My\x00  Base ",
                              brand=" Brand ")
    assert item.product_name == "My Base" and item.brand == "Brand"
    assert item.base is None and item.source == "custom"


def test_catalog_item_requires_matching_shade(test_catalog):
    product = test_catalog.products["fx-foundation-a"]
    with pytest.raises(RoutineError):
        item_from_catalog(product, None)
    with pytest.raises(RoutineError):
        item_from_catalog(product, test_catalog.shades["fx-foundation-b-medium-cool"])
    item = item_from_catalog(product, test_catalog.shades["fx-foundation-a-medium-warm"])
    assert item.base.value == "silicone" and item.source == "catalog"


def test_add_edit_remove(test_catalog):
    inv = ()
    a = custom("lipstick")
    inv = add_item(inv, a)
    with pytest.raises(RoutineError):
        add_item(inv, a)
    inv = update_item(inv, a.item_id, product_name="Renamed", formulation="liquid")
    assert inv[0].product_name == "Renamed" and inv[0].formulation is Formulation.LIQUID
    with pytest.raises(RoutineError):
        update_item(inv, a.item_id, product_name="")
    inv = remove_item(inv, a.item_id)
    assert inv == ()
    with pytest.raises(RoutineError):
        remove_item(inv, a.item_id)


def test_duplicate_catalog_shade_rejected(test_catalog):
    product = test_catalog.products["fx-primer-silicone"]
    inv = add_item((), item_from_catalog(product, None))
    with pytest.raises(RoutineError):
        add_item(inv, item_from_catalog(product, None))


# ----------------------------------------------------------------- generation
def test_empty_inventory_error(production_rules):
    with pytest.raises(RoutineError) as exc:
        gen((), rules=production_rules)
    assert exc.value.code == "empty_inventory"


def test_invalid_look(production_rules):
    with pytest.raises(RoutineError) as exc:
        gen([custom("lipstick")], look="clubbing", rules=production_rules)
    assert exc.value.code == "invalid_look"


def test_only_inventory_items_are_referenced(production_rules):
    inv = [custom("foundation"), custom("lipstick")]
    routine = gen(inv, look="glam", rules=production_rules)
    ids = {i.item_id for i in inv}
    assert [s.number for s in routine.steps] == [1, 2]
    assert all(s.item.item_id in ids for s in routine.steps)
    assert all("Optional suggestion" in s for s in routine.suggestions)  # labelled optional


def test_custom_unknown_formulation_gets_general_technique(production_rules):
    routine = gen([custom("foundation")], rules=production_rules)
    step = routine.steps[0]
    assert step.technique_note == UNKNOWN_FORMULATION_NOTE
    assert step.compatibility_notes == ()


def test_formulation_specific_technique(production_rules):
    routine = gen([custom("foundation", formulation="stick")], rules=production_rules)
    assert "Swipe" in routine.steps[0].technique and routine.steps[0].technique_note is None


def test_default_full_order(production_rules):
    assert order(gen(full_inventory(), rules=production_rules)) == [
        "skin_prep", "primer", "color_corrector", "foundation", "concealer", "powder", "blush",
        "eyeshadow", "eyeliner", "mascara", "lip_liner", "lipstick", "setting_spray",
    ]


def test_every_active_constraint_satisfied(production_rules):
    from src.routine.application_order import OrderingContext, constraint_active

    for look in Look:
        routine = gen(full_inventory(), look=look.value, rules=production_rules)
        pos = {s: i for i, s in enumerate(order(routine))}
        ctx = OrderingContext(look=look, formulations={
            s.step_id: s.item.formulation for s in routine.steps})
        for c in production_rules.ordering:
            if constraint_active(c, ctx) and c.before in pos and c.after in pos:
                assert pos[c.before] < pos[c.after], (look, c.constraint_id)


def test_cream_blush_before_powder_and_powder_blush_after(production_rules):
    cream = order(gen([custom("powder", formulation="powder"),
                       custom("blush", formulation="cream"),
                       custom("foundation", formulation="liquid")], rules=production_rules))
    assert cream.index("blush") < cream.index("powder")
    powder = order(gen([custom("powder", formulation="powder"),
                        custom("blush", formulation="powder"),
                        custom("foundation", formulation="liquid")], rules=production_rules))
    assert powder.index("powder") < powder.index("blush")


def test_concealer_order_preference(production_rules):
    inv = [custom("foundation"), custom("concealer")]
    after = order(gen(inv, rules=production_rules))
    before = order(gen(inv, rules=production_rules, preferences=RoutinePreferences(
        concealer_order=ConcealerOrder.BEFORE_FOUNDATION)))
    assert after == ["foundation", "concealer"] and before == ["concealer", "foundation"]


def test_glam_does_eyes_first(production_rules):
    inv = [custom("foundation"), custom("eyeshadow"), custom("powder")]
    assert order(gen(inv, look="glam", rules=production_rules)).index("eyeshadow") == 0
    assert order(gen(inv, look="office", rules=production_rules))[-1] == "eyeshadow"


def test_transitive_order_with_absent_intermediate(production_rules):
    # skin_prep → primer → color_corrector → foundation; primer and corrector absent.
    inv = [custom("foundation"), custom("skin_prep")]
    assert order(gen(inv, rules=production_rules)) == ["skin_prep", "foundation"]


def test_setting_spray_last(production_rules):
    inv = [custom("setting_spray"), custom("mascara"), custom("lipstick"), custom("eyebrow")]
    assert order(gen(inv, rules=production_rules))[-1] == "setting_spray"


def test_optional_steps_marked(production_rules):
    routine = gen([custom("setting_spray"), custom("lipstick")], look="everyday",
                  rules=production_rules)
    spray = next(s for s in routine.steps if s.step_id == "setting_spray")
    lip = next(s for s in routine.steps if s.step_id == "lipstick")
    assert spray.optional and spray.optional_reason
    assert not lip.optional
    glam = gen([custom("setting_spray")], look="glam", rules=production_rules)
    assert not glam.steps[0].optional


def test_missing_optional_product_suggested_not_numbered(production_rules):
    routine = gen([custom("foundation")], look="festive", rules=production_rules)
    assert order(routine) == ["foundation"]
    assert any("setting spray" in s for s in routine.suggestions)


def test_look_specific_rule_filtering(production_rules):
    inv = [custom("eyeliner", formulation="liquid")]
    office = gen(inv, look="office", rules=production_rules).steps[0]
    glam = gen(inv, look="glam", rules=production_rules).steps[0]
    assert "R-LNR-OFFICE" in office.applied_rule_ids and "R-LNR-GLAM" not in office.applied_rule_ids
    assert "R-LNR-GLAM" in glam.applied_rule_ids


def test_preference_rule(production_rules):
    routine = gen([custom("foundation")], rules=production_rules,
                  preferences=RoutinePreferences(coverage=Coverage.FULL))
    assert "R-FND-COVER-FULL" in routine.steps[0].applied_rule_ids


def test_requires_steps_dependency(production_rules):
    with_liner = gen([custom("lipstick"), custom("lip_liner")], look="glam",
                     rules=production_rules)
    without = gen([custom("lipstick")], look="glam", rules=production_rules)
    lip_with = next(s for s in with_liner.steps if s.step_id == "lipstick")
    assert "R-LIP-WITH-LINER" in lip_with.applied_rule_ids
    assert "R-LIP-WITH-LINER" not in without.steps[0].applied_rule_ids


def test_feature_tips_only_for_usable_features(production_rules):
    inv = [custom("blush"), custom("eyeliner")]
    confirmed = {FACE_SHAPE: FeatureEstimate(FACE_SHAPE, FeatureStatus.USER_CONFIRMED,
                                             value="round"),
                 EYE_SHAPE: FeatureEstimate(EYE_SHAPE, FeatureStatus.ESTIMATED, value="hooded")}
    routine = gen(inv, rules=production_rules, features=confirmed)
    blush = next(s for s in routine.steps if s.step_id == "blush")
    liner = next(s for s in routine.steps if s.step_id == "eyeliner")
    assert any("round faces" in t for t in blush.feature_tips)
    assert any("hooded" in t for t in liner.feature_tips)

    uncertain = {FACE_SHAPE: FeatureEstimate(FACE_SHAPE, FeatureStatus.UNCERTAIN,
                                             candidates=("round", "oval"))}
    routine = gen(inv, rules=production_rules, features=uncertain)
    assert all(s.feature_tips == () for s in routine.steps)
    assert any("face shape" in n for n in routine.notes)


def test_compatibility_note_requires_metadata(test_catalog, production_rules):
    primer = item_from_catalog(test_catalog.products["fx-primer-silicone"], None)
    water_fnd = item_from_catalog(test_catalog.products["fx-foundation-b"],
                                  test_catalog.shades["fx-foundation-b-medium-cool"])
    routine = gen([primer, water_fnd], rules=production_rules)
    fnd = next(s for s in routine.steps if s.step_id == "foundation")
    assert any("silicone-based" in n for n in fnd.compatibility_notes)
    routine = gen([primer, custom("foundation")], rules=production_rules)
    assert next(s for s in routine.steps if s.step_id == "foundation").compatibility_notes == ()


def test_alternatives_listed(production_rules):
    a, b = custom("lipstick", "First"), custom("lipstick", "Second")
    routine = gen([a, b], rules=production_rules)
    assert len(routine.steps) == 1
    assert routine.steps[0].item.item_id == a.item_id
    assert routine.steps[0].alternatives == (b,)


def test_signature_changes_with_inputs(production_rules):
    inv = (custom("lipstick"),)
    base = request_signature(RoutineRequest(inv, "everyday"))
    assert base == request_signature(RoutineRequest(inv, Look.EVERYDAY))
    assert base != request_signature(RoutineRequest(inv, "glam"))
    assert base != request_signature(RoutineRequest(inv + (custom("blush"),), "everyday"))
    assert base != request_signature(RoutineRequest(
        inv, "everyday", RoutinePreferences(coverage=Coverage.FULL)))


def test_deterministic(production_rules):
    inv = full_inventory()
    assert gen(inv, rules=production_rules) == gen(inv, rules=production_rules)


def test_every_category_supported(production_rules):
    inv = [custom(c.value) for c in Category]
    for look in Look:
        assert len(gen(inv, look=look.value, rules=production_rules).steps) == len(Category)
