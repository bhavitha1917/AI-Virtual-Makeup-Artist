"""Human-readable explanations generated strictly from evaluated score components."""

from __future__ import annotations

from src.core.enums import Category, VerificationStatus
from src.core.features import SKIN_DEPTH, UNDERTONE, FeatureStatus, UserProfile
from src.recommendation.ranking import RankedCandidate, ScoreComponent

FOUNDATION_DISCLAIMER = (
    "Image-based and profile-based matching cannot guarantee a shade match. Test foundation "
    "and concealer on your jawline in natural daylight before buying."
)
DEMO_CAVEAT = "Demonstration product — fictional, not available to buy."

NAMES = {
    "depth": "depth", "undertone": "undertone", "finish": "finish", "coverage": "coverage",
    "purpose": "purpose", "target": "correction target",
    "depth_suitability": "depth range", "look": "look", "color_family": "colour family",
    "intensity": "intensity", "formulation": "formula type",
}


def _h(text: str | None) -> str:
    return (text or "").replace("_", " ")


def component_sentence(c: ScoreComponent) -> str | None:
    """One sentence describing what this component compared; ``None`` for unset prefs."""
    u, i = _h(c.user_value), _h(c.item_value)
    if c.outcome == "unset":
        return None
    if c.outcome == "missing":
        return f"This item does not list a {NAMES[c.name]}, so {NAMES[c.name]} fit could not " \
               "be assessed."
    if c.name == "depth":
        return {
            "match": f"Listed depth '{i}' matches your depth ('{u}').",
            "lighter": f"Listed depth '{i}' is one level lighter than your depth ('{u}'), "
                       "which suits under-eye brightening.",
            "adjacent": f"Listed depth '{i}' is one level from your depth ('{u}').",
        }.get(c.outcome, f"Listed depth '{i}' differs from your depth ('{u}').")
    if c.name == "undertone":
        return {
            "match": f"Listed undertone '{i}' matches your undertone ('{u}').",
            "related": f"Listed undertone '{i}' is compatible with your '{u}' undertone "
                       "(neutral pairs with either).",
        }.get(c.outcome, f"Listed undertone '{i}' differs from your undertone ('{u}').")
    if c.name == "depth_suitability":
        return (f"Listed for depths: {i} — includes your depth ('{u}')." if c.outcome == "match"
                else f"Listed for depths: {i} — does not include your depth ('{u}').")
    if c.name == "look":
        return (f"Listed as suitable for the '{u}' look." if c.outcome == "match"
                else f"Not listed for the '{u}' look (listed: {i}).")
    if c.name == "purpose":
        return (f"Intended for {u} use, as you selected." if c.outcome == "match"
                else f"Intended for {i} use rather than {u}.")
    if c.name == "target":
        return f"Formulated to correct {i}, as you selected."
    label = NAMES[c.name]
    return {
        "match": f"The {label} '{i}' matches your preference.",
        "related": f"The {label} '{i}' is close to your preferred '{u}'.",
        "adjacent": f"The {label} '{i}' is one step from your preferred '{u}'.",
    }.get(c.outcome, f"The {label} '{i}' differs from your preferred '{u}'.")


def build_explanation(ranked: RankedCandidate) -> tuple[str, ...]:
    """Reasons ordered by contribution (largest first), derived only from components."""
    ordered = sorted(ranked.components, key=lambda c: (-c.contribution, c.name))
    return tuple(s for c in ordered if (s := component_sentence(c)))


def build_caveats(category: Category, ranked: RankedCandidate, profile: UserProfile
                  ) -> tuple[str, ...]:
    caveats: list[str] = []
    for comp in ranked.components:
        if comp.user_uncertain:
            caveats.append(f"Your {NAMES[comp.name].split()[0]} estimate is uncertain; "
                           "confirm it to refine these results.")
        if comp.name == "undertone" and comp.outcome == "unset":
            caveats.append("Your undertone is not set, so undertone did not affect this "
                           "ranking.")
    used = {c.name for c in ranked.components}
    for feature, comp_names in ((SKIN_DEPTH, {"depth", "depth_suitability"}),
                                (UNDERTONE, {"undertone"})):
        est = profile.get(feature)
        if used & comp_names and est.status is FeatureStatus.ESTIMATED:
            caveats.append(f"Your {feature.replace('_', ' ')} is an image-based estimate that "
                           "you have not confirmed.")
    if ranked.candidate.shade.verification_status is VerificationStatus.DEMO:
        caveats.append(DEMO_CAVEAT)
    if category in (Category.FOUNDATION, Category.CONCEALER):
        caveats.append(FOUNDATION_DISCLAIMER)
    return tuple(dict.fromkeys(caveats))


def unset_preferences(ranked: RankedCandidate) -> tuple[str, ...]:
    return tuple(NAMES[c.name] for c in ranked.components if c.outcome == "unset")
