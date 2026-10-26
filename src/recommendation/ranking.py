"""Category-specific weighted scoring of candidates that passed the hard filters.

Each component score is in [0, 1]. Missing item metadata scores 0 (never rewarded); an
unset user preference scores 0.5 for every candidate (non-discriminating). The total is
a weighted sum in [0, 1] used only for ranking — it is not a probability.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from src.config import SETTINGS
from src.core.enums import Category, ColorFamily, ConcealerPurpose, Finish, Undertone
from src.core.features import SKIN_DEPTH, UNDERTONE, FeatureStatus, UserProfile
from src.recommendation.preferences import RecommendationPreferences
from src.recommendation.product_matcher import Candidate, user_depths, user_undertones

WEIGHTS: Mapping[Category, Mapping[str, float]] = MappingProxyType({
    Category.FOUNDATION: {"depth": 0.45, "undertone": 0.30, "finish": 0.15, "coverage": 0.10},
    Category.CONCEALER: {"depth": 0.45, "undertone": 0.25, "purpose": 0.20, "finish": 0.10},
    Category.COLOR_CORRECTOR: {"target": 0.60, "depth_suitability": 0.40},
    Category.LIPSTICK: {"look": 0.35, "color_family": 0.30, "intensity": 0.20, "finish": 0.15},
    Category.BLUSH: {"look": 0.35, "color_family": 0.30, "intensity": 0.20, "formulation": 0.15},
    Category.EYELINER: {"look": 0.40, "color_family": 0.35, "formulation": 0.25},
})

UNSET = 0.5

RELATED_FINISHES = frozenset({
    frozenset({Finish.NATURAL, Finish.SATIN}),
    frozenset({Finish.DEWY, Finish.RADIANT}),
    frozenset({Finish.GLOSS, Finish.SHIMMER}),
})
RELATED_COLORS = frozenset(frozenset(pair) for pair in (
    (ColorFamily.NUDE, ColorFamily.BROWN), (ColorFamily.NUDE, ColorFamily.PEACH),
    (ColorFamily.PINK, ColorFamily.ROSE), (ColorFamily.ROSE, ColorFamily.BERRY),
    (ColorFamily.RED, ColorFamily.BERRY), (ColorFamily.BERRY, ColorFamily.PLUM),
    (ColorFamily.CORAL, ColorFamily.PEACH), (ColorFamily.CORAL, ColorFamily.ORANGE),
    (ColorFamily.PEACH, ColorFamily.TERRACOTTA), (ColorFamily.TERRACOTTA, ColorFamily.BRONZE),
    (ColorFamily.BROWN, ColorFamily.BRONZE),
))


@dataclass(frozen=True)
class ScoreComponent:
    """One evaluated criterion. ``outcome`` is a machine-readable result used by
    ``explanations`` so that every sentence maps to an evaluated comparison."""

    name: str
    weight: float
    score: float
    outcome: str  # match | related | adjacent | lighter | mismatch | missing | unset | ...
    user_value: str | None = None
    item_value: str | None = None
    user_uncertain: bool = False

    @property
    def contribution(self) -> float:
        return self.weight * self.score


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: float
    components: tuple[ScoreComponent, ...]

    @property
    def label(self) -> str:
        cfg = SETTINGS.recommendation
        if self.score >= cfg.strong_fit:
            return "Strong fit"
        if self.score >= cfg.good_fit:
            return "Good fit"
        return "Partial fit"


def _val(x: object) -> str | None:
    return getattr(x, "value", None) if x is not None else None


def _depth(cand: Candidate, profile: UserProfile, prefs: RecommendationPreferences,
           category: Category, w: float) -> ScoreComponent:
    shade_depth = cand.shade.depth
    depths = user_depths(profile)
    uncertain = profile.get(SKIN_DEPTH).status is FeatureStatus.UNCERTAIN
    if shade_depth is None or not depths:  # excluded by filters; defensive
        return ScoreComponent("depth", w, 0.0, "missing", None, _val(shade_depth), uncertain)
    brightening = (category is Category.CONCEALER and
                   prefs.concealer_purpose is ConcealerPurpose.BRIGHTENING)
    best: tuple[float, str, str] = (0.0, "mismatch", depths[0].value)
    for d in depths:
        diff = d.index - shade_depth.index  # positive: shade is lighter than the user
        if brightening:
            option = (1.0, "lighter", d.value) if diff == 1 else \
                (0.8, "match", d.value) if diff == 0 else (0.0, "mismatch", d.value)
        else:
            option = (1.0, "match", d.value) if diff == 0 else \
                (0.4, "adjacent", d.value) if abs(diff) == 1 else (0.0, "mismatch", d.value)
        best = max(best, option, key=lambda o: o[0])
    return ScoreComponent("depth", w, best[0], best[1], best[2], shade_depth.value, uncertain)


def _undertone(cand: Candidate, profile: UserProfile, w: float) -> ScoreComponent:
    shade_ut = cand.shade.undertone
    tones = user_undertones(profile)
    uncertain = profile.get(UNDERTONE).status is FeatureStatus.UNCERTAIN
    if not tones:
        return ScoreComponent("undertone", w, UNSET, "unset", None, _val(shade_ut))
    if shade_ut is None:
        return ScoreComponent("undertone", w, 0.0, "missing", tones[0].value, None, uncertain)
    best = (0.0, "mismatch", tones[0].value)
    for t in tones:
        if t is shade_ut:
            option = (1.0, "match", t.value)
        elif Undertone.NEUTRAL in (t, shade_ut):
            option = (0.5, "related", t.value)
        else:
            option = (0.0, "mismatch", t.value)
        best = max(best, option, key=lambda o: o[0])
    return ScoreComponent("undertone", w, best[0], best[1], best[2], shade_ut.value, uncertain)


def _finish(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    item = cand.shade.finish or cand.product.finish
    if prefs.finish is None:
        return ScoreComponent("finish", w, UNSET, "unset", None, _val(item))
    if item is None:
        return ScoreComponent("finish", w, 0.0, "missing", prefs.finish.value, None)
    if item is prefs.finish:
        return ScoreComponent("finish", w, 1.0, "match", prefs.finish.value, item.value)
    if frozenset({item, prefs.finish}) in RELATED_FINISHES:
        return ScoreComponent("finish", w, 0.5, "related", prefs.finish.value, item.value)
    return ScoreComponent("finish", w, 0.0, "mismatch", prefs.finish.value, item.value)


def _coverage(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    item = cand.product.coverage
    if prefs.coverage is None:
        return ScoreComponent("coverage", w, UNSET, "unset", None, _val(item))
    if item is None:
        return ScoreComponent("coverage", w, 0.0, "missing", prefs.coverage.value, None)
    diff = abs(item.index - prefs.coverage.index)
    outcome = "match" if diff == 0 else "adjacent" if diff == 1 else "mismatch"
    return ScoreComponent("coverage", w, round(1 - diff / 3, 4), outcome,
                          prefs.coverage.value, item.value)


def _purpose(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    purpose = prefs.concealer_purpose.value
    uses = cand.product.intended_use
    if not uses:
        return ScoreComponent("purpose", w, 0.0, "missing", purpose, None)
    ok = purpose in uses
    return ScoreComponent("purpose", w, 1.0 if ok else 0.0, "match" if ok else "mismatch",
                          purpose, ", ".join(uses))


def _target(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    target = cand.shade.correction_target
    ok = target is not None and target is prefs.correction_target
    return ScoreComponent("target", w, 1.0 if ok else 0.0, "match" if ok else "mismatch",
                          _val(prefs.correction_target), _val(target))


def _depth_suitability(cand: Candidate, profile: UserProfile, w: float) -> ScoreComponent:
    depths = user_depths(profile)
    uncertain = profile.get(SKIN_DEPTH).status is FeatureStatus.UNCERTAIN
    suitable = cand.shade.suitable_depths
    listed = ", ".join(d.value for d in suitable) or None
    if not depths:
        return ScoreComponent("depth_suitability", w, UNSET, "unset", None, listed)
    if not suitable:
        return ScoreComponent("depth_suitability", w, 0.0, "missing", depths[0].value, None,
                              uncertain)
    hit = next((d for d in depths if d in suitable), None)
    if hit:
        return ScoreComponent("depth_suitability", w, 1.0, "match", hit.value, listed, uncertain)
    return ScoreComponent("depth_suitability", w, 0.0, "mismatch", depths[0].value, listed,
                          uncertain)


def _look(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    looks = cand.shade.suitable_looks
    listed = ", ".join(lk.value for lk in looks) or None
    if prefs.look is None:
        return ScoreComponent("look", w, UNSET, "unset", None, listed)
    if not looks:
        return ScoreComponent("look", w, 0.0, "missing", prefs.look.value, None)
    ok = prefs.look in looks
    return ScoreComponent("look", w, 1.0 if ok else 0.0, "match" if ok else "mismatch",
                          prefs.look.value, listed)


def _color(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    item = cand.shade.color_family
    if prefs.color_family is None:
        return ScoreComponent("color_family", w, UNSET, "unset", None, _val(item))
    if item is None:
        return ScoreComponent("color_family", w, 0.0, "missing", prefs.color_family.value, None)
    if item is prefs.color_family:
        return ScoreComponent("color_family", w, 1.0, "match", prefs.color_family.value,
                              item.value)
    if frozenset({item, prefs.color_family}) in RELATED_COLORS:
        return ScoreComponent("color_family", w, 0.5, "related", prefs.color_family.value,
                              item.value)
    return ScoreComponent("color_family", w, 0.0, "mismatch", prefs.color_family.value,
                          item.value)


def _intensity(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    item = cand.shade.intensity
    if prefs.intensity is None:
        return ScoreComponent("intensity", w, UNSET, "unset", None, _val(item))
    if item is None:
        return ScoreComponent("intensity", w, 0.0, "missing", prefs.intensity.value, None)
    diff = abs(item.index - prefs.intensity.index)
    outcome = "match" if diff == 0 else "adjacent" if diff == 1 else "mismatch"
    return ScoreComponent("intensity", w, round(1 - diff / 2, 4), outcome,
                          prefs.intensity.value, item.value)


def _formulation(cand: Candidate, prefs: RecommendationPreferences, w: float) -> ScoreComponent:
    item = cand.product.formulation
    if prefs.formulation is None:
        return ScoreComponent("formulation", w, UNSET, "unset", None, _val(item))
    if item is None:
        return ScoreComponent("formulation", w, 0.0, "missing", prefs.formulation.value, None)
    ok = item is prefs.formulation
    return ScoreComponent("formulation", w, 1.0 if ok else 0.0, "match" if ok else "mismatch",
                          prefs.formulation.value, item.value)


_Scorer = Callable[[Candidate, UserProfile, RecommendationPreferences, Category, float],
                   ScoreComponent]
SCORERS: Mapping[str, _Scorer] = MappingProxyType({
    "depth": lambda c, pr, pf, cat, w: _depth(c, pr, pf, cat, w),
    "undertone": lambda c, pr, pf, cat, w: _undertone(c, pr, w),
    "finish": lambda c, pr, pf, cat, w: _finish(c, pf, w),
    "coverage": lambda c, pr, pf, cat, w: _coverage(c, pf, w),
    "purpose": lambda c, pr, pf, cat, w: _purpose(c, pf, w),
    "target": lambda c, pr, pf, cat, w: _target(c, pf, w),
    "depth_suitability": lambda c, pr, pf, cat, w: _depth_suitability(c, pr, w),
    "look": lambda c, pr, pf, cat, w: _look(c, pf, w),
    "color_family": lambda c, pr, pf, cat, w: _color(c, pf, w),
    "intensity": lambda c, pr, pf, cat, w: _intensity(c, pf, w),
    "formulation": lambda c, pr, pf, cat, w: _formulation(c, pf, w),
})


def score_candidate(category: Category, cand: Candidate, profile: UserProfile,
                    prefs: RecommendationPreferences) -> RankedCandidate:
    weights = WEIGHTS[category]
    components = tuple(SCORERS[name](cand, profile, prefs, category, w)
                       for name, w in weights.items())
    total = round(sum(c.contribution for c in components), 3)
    return RankedCandidate(cand, total, components)


def rank_candidates(category: Category, candidates: tuple[Candidate, ...] | list[Candidate],
                    profile: UserProfile, prefs: RecommendationPreferences
                    ) -> list[RankedCandidate]:
    ranked = [score_candidate(category, c, profile, prefs) for c in candidates]
    ranked.sort(key=lambda r: (-r.score, *r.candidate.sort_key))
    return ranked
