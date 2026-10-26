"""Recommendation entry point used by the UI."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import SETTINGS
from src.core.enums import RECOMMENDABLE_CATEGORIES, Category
from src.core.errors import BeautyStudioError
from src.core.features import UserProfile
from src.data.schema import Catalog, Product, Shade
from src.recommendation.explanations import (
    build_caveats,
    build_explanation,
    unset_preferences,
)
from src.recommendation.preferences import RecommendationPreferences
from src.recommendation.product_matcher import (
    REJECT_REASONS,
    apply_hard_filters,
    iter_candidates,
)
from src.recommendation.ranking import RankedCandidate, ScoreComponent, rank_candidates


@dataclass(frozen=True)
class Recommendation:
    product: Product
    shade: Shade
    score: float
    label: str
    components: tuple[ScoreComponent, ...]
    reasons: tuple[str, ...]
    caveats: tuple[str, ...]
    unset_preferences: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationResult:
    category: Category
    status: str  # "ok" | "empty" | "needs_input"
    items: tuple[Recommendation, ...]
    message: str
    suggestions: tuple[str, ...] = ()
    total_candidates: int = 0
    eligible_candidates: int = 0


def _to_recommendation(category: Category, ranked: RankedCandidate, profile: UserProfile
                       ) -> Recommendation:
    return Recommendation(
        product=ranked.candidate.product,
        shade=ranked.candidate.shade,
        score=ranked.score,
        label=ranked.label,
        components=ranked.components,
        reasons=build_explanation(ranked),
        caveats=build_caveats(category, ranked, profile),
        unset_preferences=unset_preferences(ranked),
    )


def recommend(category: Category, profile: UserProfile, prefs: RecommendationPreferences,
              catalog: Catalog, limit: int | None = None) -> RecommendationResult:
    """Filter, rank and explain catalog shades for one category.

    Essential compatibility filters are never relaxed; if nothing passes, an ``empty``
    result explains which filters excluded the candidates.
    """
    if category not in RECOMMENDABLE_CATEGORIES:
        raise BeautyStudioError("unsupported_category",
                                f"Recommendations are not available for {category.value}.")
    limit = limit or SETTINGS.recommendation.default_limit
    candidates = iter_candidates(catalog, category)
    if not candidates:
        return RecommendationResult(
            category, "empty", (), f"The catalog has no {category.value} products yet.",
            total_candidates=0)
    outcome = apply_hard_filters(category, candidates, profile, prefs)
    if outcome.needs_input:
        return RecommendationResult(category, "needs_input", (), outcome.needs_input,
                                    total_candidates=len(candidates))
    if not outcome.passed:
        reasons = "; ".join(
            f"{count} because {REJECT_REASONS[key]}"
            for key, count in sorted(outcome.rejected.items())
        )
        return RecommendationResult(
            category, "empty", (),
            f"No suitable catalog match was found. {len(candidates)} shades were checked: "
            f"{reasons}.",
            suggestions=(
                "Check that your depth and undertone are set correctly.",
                "If your estimate was uncertain, confirming it may change the results.",
                "The demonstration catalog is small; a real catalog would cover more shades.",
            ),
            total_candidates=len(candidates), eligible_candidates=0,
        )
    ranked = rank_candidates(category, outcome.passed, profile, prefs)[:limit]
    items = tuple(_to_recommendation(category, r, profile) for r in ranked)
    return RecommendationResult(
        category, "ok", items,
        f"Showing the top {len(items)} of {len(outcome.passed)} eligible shades.",
        total_candidates=len(candidates), eligible_candidates=len(outcome.passed),
    )
