"""Rule selection and semantic validation of tutorial rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from src.config import DATA_DIR
from src.core.enums import Formulation, Look
from src.core.errors import CatalogError
from src.data.loader import load_tutorial_rules
from src.data.schema import TutorialRule, TutorialRules
from src.routine.application_order import find_any_context_cycle

FEATURE_CONDITION_KEYS = frozenset({"face_shape", "eye_shape", "eye_tilt"})
PREFERENCE_CONDITION_KEYS = frozenset({"coverage", "intensity", "concealer_order"})


@dataclass(frozen=True)
class RuleContext:
    look: Look
    present_steps: frozenset[str]
    features: Mapping[str, str] = field(default_factory=dict)  # usable feature values only
    preferences: Mapping[str, str] = field(default_factory=dict)


def rule_applies(rule: TutorialRule, step_id: str, ctx: RuleContext,
                 formulation: Formulation | None) -> bool:
    if rule.step_id != step_id:
        return False
    if rule.looks is not None and ctx.look not in rule.looks:
        return False
    if any(dep not in ctx.present_steps for dep in rule.requires_steps):
        return False
    for key, allowed in rule.conditions.items():
        if key in FEATURE_CONDITION_KEYS:
            actual = ctx.features.get(key)
        elif key in PREFERENCE_CONDITION_KEYS:
            actual = ctx.preferences.get(key)
        elif key == "formulation":
            actual = formulation.value if formulation else None
        else:  # unknown keys are rejected at load time; be safe at runtime
            return False
        if actual not in allowed:
            return False
    return True


def select_rules(step_id: str, ctx: RuleContext, rules: tuple[TutorialRule, ...],
                 formulation: Formulation | None) -> list[TutorialRule]:
    """Applicable rules for a step; within an exclusive group the highest priority wins."""
    applicable = [r for r in rules if rule_applies(r, step_id, ctx, formulation)]
    applicable.sort(key=lambda r: (-r.priority, r.rule_id))
    chosen: list[TutorialRule] = []
    used_groups: set[str] = set()
    for rule in applicable:
        if rule.exclusive_group:
            if rule.exclusive_group in used_groups:
                continue
            used_groups.add(rule.exclusive_group)
        chosen.append(rule)
    return chosen


def feature_tips(step_id: str, features: Mapping[str, str], tutorial: TutorialRules
                 ) -> list[str]:
    """Feature-based tips for one step, independent of inventory and look.

    ``features`` must contain only usable (estimated or confirmed) values. Used by the
    Shade Finder to show eyeliner technique guidance for the user's eye shape.
    """
    ctx = RuleContext(look=Look.EVERYDAY, present_steps=frozenset(), features=features)
    candidates = tuple(r for r in tutorial.rules if r.kind == "feature" and r.looks is None
                       and not r.requires_steps)
    return [r.instruction for r in select_rules(step_id, ctx, candidates, None)]


def _could_co_apply(a: TutorialRule, b: TutorialRule) -> bool:
    if a.looks is not None and b.looks is not None and not (a.looks & b.looks):
        return False
    for key in set(a.conditions) & set(b.conditions):
        if not (a.conditions[key] & b.conditions[key]):
            return False
    return True


def find_contradictions(rules: tuple[TutorialRule, ...]) -> list[str]:
    """Rules in the same exclusive group with equal priority that can both apply are
    contradictory: neither could be preferred deterministically on principle."""
    issues = []
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            if (a.step_id == b.step_id and a.exclusive_group and
                    a.exclusive_group == b.exclusive_group and a.priority == b.priority and
                    _could_co_apply(a, b)):
                issues.append(
                    f"rules {a.rule_id} and {b.rule_id} contradict: same step, exclusive group "
                    f"{a.exclusive_group!r} and priority {a.priority}, with overlapping conditions"
                )
    return issues


def validate_rules(tutorial: TutorialRules) -> None:
    """Semantic validation: contradictions and ordering cycles in any reachable context."""
    issues = find_contradictions(tutorial.rules)
    sequence = {s.step_id: s.sequence for s in tutorial.steps.values()}
    cyclic = find_any_context_cycle(sequence, tutorial.ordering)
    if cyclic:
        desc, cycle = cyclic
        issues.append(f"ordering cycle {' → '.join(cycle)} when {desc}")
    if issues:
        raise CatalogError(issues)


def load_validated_rules(data_dir: Path = DATA_DIR) -> TutorialRules:
    rules = load_tutorial_rules(data_dir)
    validate_rules(rules)
    return rules
