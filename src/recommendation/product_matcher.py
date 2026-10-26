"""Candidate generation and category-specific *hard* compatibility filters.

Hard filters decide eligibility; soft preferences are handled only in ``ranking``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from src.core.enums import (
    COMPLEXION_CATEGORIES,
    Category,
    ConcealerPurpose,
    Depth,
    Undertone,
    VerificationStatus,
)
from src.core.features import SKIN_DEPTH, UNDERTONE, UserProfile
from src.data.schema import Catalog, Product, Shade
from src.recommendation.preferences import RecommendationPreferences

OPPOSITE_UNDERTONE = {Undertone.COOL: Undertone.WARM, Undertone.WARM: Undertone.COOL}


@dataclass(frozen=True)
class Candidate:
    product: Product
    shade: Shade

    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.product.product_id, self.shade.shade_id)


@dataclass(frozen=True)
class FilterOutcome:
    passed: tuple[Candidate, ...]
    rejected: Counter = field(default_factory=Counter)
    needs_input: str | None = None


REJECT_REASONS = {
    "unverified": "shade metadata is not verified",
    "depth_missing": "the shade does not list a depth",
    "depth_far": "the shade depth is more than one level from your depth",
    "depth_purpose": "the shade is darker than your depth (brightening concealer)",
    "undertone_opposite": "the listed undertone is opposite to yours",
    "target": "the corrector targets a different concern",
}


def iter_candidates(catalog: Catalog, category: Category) -> list[Candidate]:
    return sorted(
        (Candidate(p, s) for p in catalog.products_in(category) for s in catalog.shades_for(p)),
        key=lambda c: c.sort_key,
    )


def user_depths(profile: UserProfile) -> tuple[Depth, ...]:
    return tuple(Depth(v) for v in profile.get(SKIN_DEPTH).possible_values)


def user_undertones(profile: UserProfile) -> tuple[Undertone, ...]:
    return tuple(Undertone(v) for v in profile.get(UNDERTONE).possible_values)


def _complexion_reject(category: Category, cand: Candidate, depths: tuple[Depth, ...],
                       undertones: tuple[Undertone, ...],
                       prefs: RecommendationPreferences) -> str | None:
    shade = cand.shade
    if shade.verification_status is VerificationStatus.UNVERIFIED:
        return "unverified"
    if shade.depth is None:
        return "depth_missing"
    if category is Category.CONCEALER and prefs.concealer_purpose is ConcealerPurpose.BRIGHTENING:
        # Same depth or exactly one level lighter.
        if not any(0 <= d.index - shade.depth.index <= 1 for d in depths):
            return "depth_purpose"
    elif min(abs(d.index - shade.depth.index) for d in depths) > 1:
        return "depth_far"
    if undertones and shade.undertone is not None and all(
        OPPOSITE_UNDERTONE.get(u) is shade.undertone for u in undertones
    ):
        return "undertone_opposite"
    return None


def apply_hard_filters(category: Category, candidates: list[Candidate], profile: UserProfile,
                       prefs: RecommendationPreferences) -> FilterOutcome:
    rejected: Counter = Counter()
    if category in (Category.FOUNDATION, Category.CONCEALER):
        depths = user_depths(profile)
        if not depths:
            return FilterOutcome((), rejected, needs_input=(
                "Set your skin depth (on Face Analysis or in your profile) to see "
                f"{category.value} shades. Shades are never suggested without a depth."))
        undertones = user_undertones(profile)
        passed = []
        for cand in candidates:
            reason = _complexion_reject(category, cand, depths, undertones, prefs)
            if reason:
                rejected[reason] += 1
            else:
                passed.append(cand)
        return FilterOutcome(tuple(passed), rejected)
    if category is Category.COLOR_CORRECTOR:
        if prefs.correction_target is None:
            return FilterOutcome((), rejected, needs_input=(
                "Choose what you want to correct (dark circles, redness or dullness)."))
        passed = []
        for cand in candidates:
            if cand.shade.verification_status is VerificationStatus.UNVERIFIED:
                rejected["unverified"] += 1
            elif cand.shade.correction_target is not prefs.correction_target:
                rejected["target"] += 1
            else:
                passed.append(cand)
        return FilterOutcome(tuple(passed), rejected)
    assert category not in COMPLEXION_CATEGORIES
    return FilterOutcome(tuple(candidates), rejected)
