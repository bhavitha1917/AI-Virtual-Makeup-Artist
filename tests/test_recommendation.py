import pytest

from src.core.enums import (
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
from src.core.errors import BeautyStudioError
from src.core.features import (
    EYE_SHAPE,
    SKIN_DEPTH,
    UNDERTONE,
    FeatureEstimate,
    FeatureStatus,
    UserProfile,
)
from src.data.loader import load_catalog
from src.recommendation.explanations import FOUNDATION_DISCLAIMER, component_sentence
from src.recommendation.preferences import RecommendationPreferences as Prefs
from src.recommendation.ranking import WEIGHTS
from src.recommendation.service import recommend


def profile(depth=None, undertone=None, status=FeatureStatus.USER_CONFIRMED, **extra):
    feats = {}
    if depth:
        feats[SKIN_DEPTH] = FeatureEstimate(SKIN_DEPTH, status, value=depth)
    if undertone:
        feats[UNDERTONE] = FeatureEstimate(UNDERTONE, status, value=undertone)
    feats.update(extra)
    return UserProfile(features=feats)


def ids(result):
    return [r.shade.shade_id for r in result.items]


def test_weights_sum_to_one():
    for category, weights in WEIGHTS.items():
        assert sum(weights.values()) == pytest.approx(1.0), category


def test_foundation_needs_depth(test_catalog):
    result = recommend(Category.FOUNDATION, profile(), Prefs(), test_catalog)
    assert result.status == "needs_input" and result.items == ()


def test_foundation_exact_match_ranks_first(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "warm"), Prefs(), test_catalog)
    assert result.status == "ok"
    assert ids(result)[0] == "fx-foundation-a-medium-warm"


def test_foundation_filters_far_depth_and_opposite_undertone(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "warm"), Prefs(), test_catalog,
                       limit=50)
    got = ids(result)
    assert "fx-foundation-a-deep-cool" not in got  # 1 level away but opposite undertone
    assert "fx-foundation-b-medium-cool" not in got  # opposite undertone
    assert "fx-foundation-a-light-cool" not in got
    assert all(r.shade.depth.value in {"light", "medium", "tan"} for r in result.items)


def test_unverified_shades_never_recommended_for_complexion(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "neutral"), Prefs(), test_catalog,
                       limit=50)
    assert "fx-foundation-c-medium-neutral" not in ids(result)


def test_unknown_undertone_does_not_discriminate(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium"), Prefs(), test_catalog, limit=50)
    by_id = {r.shade.shade_id: r for r in result.items}
    warm = next(c for c in by_id["fx-foundation-a-medium-warm"].components if c.name == "undertone")
    cool = next(c for c in by_id["fx-foundation-b-medium-cool"].components if c.name == "undertone")
    assert warm.score == cool.score == 0.5 and warm.outcome == "unset"
    assert any("undertone is not set" in c for c in by_id["fx-foundation-a-medium-warm"].caveats)


def test_missing_metadata_is_not_rewarded(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "neutral"), Prefs(), test_catalog,
                       limit=50)
    by_id = {r.shade.shade_id: r for r in result.items}
    missing = by_id["fx-foundation-a-medium-none"]
    listed = by_id["fx-foundation-a-medium-neutral"]
    assert missing.score < listed.score
    ut = next(c for c in missing.components if c.name == "undertone")
    assert ut.score == 0.0 and ut.outcome == "missing"
    assert any("does not list a undertone" in r or "does not list a" in r for r in missing.reasons)


def test_uncertain_depth_uses_candidates_and_warns(test_catalog):
    uncertain = FeatureEstimate(SKIN_DEPTH, FeatureStatus.UNCERTAIN, candidates=("light", "medium"))
    result = recommend(Category.FOUNDATION, UserProfile({SKIN_DEPTH: uncertain}), Prefs(),
                       test_catalog, limit=50)
    assert result.status == "ok"
    assert any("uncertain" in c for c in result.items[0].caveats)


def test_estimated_value_is_flagged_as_unconfirmed(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "warm", FeatureStatus.ESTIMATED),
                       Prefs(), test_catalog)
    assert any("not confirmed" in c for c in result.items[0].caveats)


def test_finish_and_coverage_preferences_reorder(test_catalog):
    p = profile("medium")
    dewy = recommend(Category.FOUNDATION, p, Prefs(finish=Finish.DEWY, coverage=Coverage.SHEER),
                     test_catalog)
    matte = recommend(Category.FOUNDATION, p, Prefs(finish=Finish.MATTE, coverage=Coverage.MEDIUM),
                      test_catalog)
    assert dewy.items[0].product.product_id == "fx-foundation-b"
    assert matte.items[0].product.product_id == "fx-foundation-a"


def test_foundation_disclaimer_present(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium"), Prefs(), test_catalog)
    assert all(FOUNDATION_DISCLAIMER in r.caveats for r in result.items)


def test_empty_result_explains_and_does_not_relax(test_catalog):
    # Rich depth: fixture catalog has nothing within one level except deep-cool, excluded by warm.
    result = recommend(Category.FOUNDATION, profile("rich", "warm"), Prefs(), test_catalog)
    assert result.status == "empty" and result.items == ()
    assert "No suitable catalog match" in result.message
    assert "opposite" in result.message or "more than one level" in result.message
    assert result.suggestions


def test_brightening_concealer_same_or_one_lighter(test_catalog):
    result = recommend(Category.CONCEALER, profile("medium", "warm"),
                       Prefs(concealer_purpose=ConcealerPurpose.BRIGHTENING), test_catalog,
                       limit=50)
    depths = {r.shade.depth.value for r in result.items}
    assert depths <= {"medium", "light"} and "tan" not in depths
    top = result.items[0]
    assert top.shade.shade_id == "fx-concealer-bright-light-warm"
    assert any("one level lighter" in s for s in top.reasons)


def test_spot_concealer_prefers_spot_products(test_catalog):
    result = recommend(Category.CONCEALER, profile("medium", "neutral"),
                       Prefs(concealer_purpose=ConcealerPurpose.SPOT), test_catalog)
    assert result.items[0].product.product_id == "fx-concealer-spot"


def test_corrector_requires_target_and_respects_depth(test_catalog):
    assert recommend(Category.COLOR_CORRECTOR, profile("deep"), Prefs(),
                     test_catalog).status == "needs_input"
    result = recommend(Category.COLOR_CORRECTOR, profile("deep"),
                       Prefs(correction_target=CorrectionTarget.DARK_CIRCLES), test_catalog)
    assert ids(result)[0] == "fx-corrector-orange"
    assert all(r.shade.correction_target is CorrectionTarget.DARK_CIRCLES for r in result.items)
    redness = recommend(Category.COLOR_CORRECTOR, profile(),
                        Prefs(correction_target=CorrectionTarget.REDNESS), test_catalog)
    assert ids(redness) == ["fx-corrector-green"]


def test_lipstick_ranks_by_look_family_intensity(test_catalog):
    result = recommend(Category.LIPSTICK, profile(),
                       Prefs(look=Look.GLAM, color_family=ColorFamily.RED,
                             intensity=Intensity.BOLD), test_catalog)
    assert ids(result)[0] == "fx-lipstick-red"
    office = recommend(Category.LIPSTICK, profile(),
                       Prefs(look=Look.OFFICE, intensity=Intensity.SOFT), test_catalog)
    assert ids(office)[0] == "fx-lipstick-nude"
    unlabelled = next(r for r in office.items if r.shade.shade_id == "fx-lipstick-unlabelled")
    assert unlabelled.score == min(r.score for r in office.items)


def test_lipstick_does_not_use_skin_rules(test_catalog):
    a = recommend(Category.LIPSTICK, profile("fair", "cool"), Prefs(look=Look.FESTIVE),
                  test_catalog)
    b = recommend(Category.LIPSTICK, profile("rich", "warm"), Prefs(look=Look.FESTIVE),
                  test_catalog)
    assert [(r.shade.shade_id, r.score) for r in a.items] == \
        [(r.shade.shade_id, r.score) for r in b.items]


def test_blush_formulation_preference(test_catalog):
    result = recommend(Category.BLUSH, profile(), Prefs(formulation=Formulation.CREAM),
                       test_catalog)
    assert result.items[0].product.product_id == "fx-blush-cream"


def test_eyeliner_color_and_type(test_catalog):
    result = recommend(Category.EYELINER, profile(),
                       Prefs(look=Look.OFFICE, color_family=ColorFamily.BROWN,
                             formulation=Formulation.PENCIL), test_catalog)
    assert ids(result)[0] == "fx-liner-pencil-brown"


def test_explanations_only_reference_evaluated_criteria(test_catalog):
    result = recommend(Category.LIPSTICK, profile(), Prefs(look=Look.GLAM), test_catalog)
    for rec in result.items:
        text = " ".join(rec.reasons).lower()
        assert "undertone" not in text and "depth" not in text  # not evaluated for lipstick
        assert "colour family" in rec.unset_preferences
        for comp in rec.components:
            sentence = component_sentence(comp)
            assert (sentence is None) == (comp.outcome == "unset")


def test_no_probability_or_percentage_claims(test_catalog):
    result = recommend(Category.FOUNDATION, profile("medium", "warm"), Prefs(), test_catalog)
    for rec in result.items:
        blob = " ".join(rec.reasons + rec.caveats).lower()
        assert "%" not in blob and "probability" not in blob and "guarantee" not in blob.replace(
            "cannot guarantee", "")
        assert rec.label in {"Strong fit", "Good fit", "Partial fit"}
        assert 0.0 <= rec.score <= 1.0


def test_deterministic(test_catalog):
    p, prefs = profile("medium", "neutral"), Prefs(finish=Finish.MATTE)
    a = recommend(Category.FOUNDATION, p, prefs, test_catalog)
    b = recommend(Category.FOUNDATION, p, prefs, test_catalog)
    assert [(r.shade.shade_id, r.score) for r in a.items] == \
        [(r.shade.shade_id, r.score) for r in b.items]


def test_empty_candidate_list(test_catalog):
    from dataclasses import replace

    empty = replace(test_catalog, products={}, shades={})
    result = recommend(Category.BLUSH, profile(), Prefs(), empty)
    assert result.status == "empty" and "no blush products" in result.message


def test_unsupported_category_rejected(test_catalog):
    with pytest.raises(BeautyStudioError):
        recommend(Category.MASCARA, profile(), Prefs(), test_catalog)


def test_eye_shape_irrelevant_to_foundation(test_catalog):
    eye = FeatureEstimate(EYE_SHAPE, FeatureStatus.USER_CONFIRMED, value="hooded")
    a = recommend(Category.FOUNDATION, profile("medium"), Prefs(), test_catalog)
    b = recommend(Category.FOUNDATION, profile("medium", **{EYE_SHAPE: eye}), Prefs(),
                  test_catalog)
    assert ids(a) == ids(b)


@pytest.mark.parametrize("category", [Category.FOUNDATION, Category.CONCEALER])
@pytest.mark.parametrize("depth", ["fair", "light", "medium", "tan", "deep", "rich"])
def test_production_catalog_covers_every_depth(category, depth):
    result = recommend(category, profile(depth, "neutral"), Prefs(), load_catalog())
    assert result.status == "ok", result.message
