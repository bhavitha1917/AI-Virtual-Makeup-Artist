"""Generate a numbered, dependency-ordered makeup routine from the user's own inventory."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from src.core.enums import ConcealerOrder, Coverage, Intensity, Look
from src.core.errors import RoutineError
from src.core.features import EYE_SHAPE, EYE_TILT, FACE_SHAPE, FeatureEstimate
from src.data.schema import StepDefinition, TutorialRules
from src.routine.application_order import OrderingContext, order_steps
from src.routine.inventory import InventoryItem
from src.routine.rule_engine import RuleContext, select_rules

UNKNOWN_FORMULATION_NOTE = (
    "Formulation not specified for this product, so a general technique is shown."
)
ROUTINE_FEATURES = (FACE_SHAPE, EYE_SHAPE, EYE_TILT)
FEATURE_STEPS = {
    FACE_SHAPE: ("blush", "bronzer"),
    EYE_SHAPE: ("eyeliner", "eyeshadow", "mascara"),
    EYE_TILT: ("eyeliner",),
}


@dataclass(frozen=True)
class RoutinePreferences:
    coverage: Coverage | None = None
    intensity: Intensity | None = None
    concealer_order: ConcealerOrder = ConcealerOrder.AFTER_FOUNDATION

    def as_conditions(self) -> dict[str, str]:
        out = {"concealer_order": self.concealer_order.value}
        if self.coverage:
            out["coverage"] = self.coverage.value
        if self.intensity:
            out["intensity"] = self.intensity.value
        return out


@dataclass(frozen=True)
class RoutineRequest:
    inventory: tuple[InventoryItem, ...]
    look: Look | str
    preferences: RoutinePreferences = field(default_factory=RoutinePreferences)
    features: Mapping[str, FeatureEstimate] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutineStep:
    number: int
    step_id: str
    title: str
    item: InventoryItem
    purpose: str
    technique: str
    technique_note: str | None
    instructions: tuple[str, ...]
    feature_tips: tuple[str, ...]
    optional: bool
    optional_reason: str | None
    compatibility_notes: tuple[str, ...]
    cautions: tuple[str, ...]
    alternatives: tuple[InventoryItem, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class SkippedStep:
    step_id: str
    title: str
    reason: str


@dataclass(frozen=True)
class Routine:
    look: Look
    look_label: str
    steps: tuple[RoutineStep, ...]
    skipped: tuple[SkippedStep, ...]
    suggestions: tuple[str, ...]
    notes: tuple[str, ...]
    general_cautions: tuple[str, ...]
    signature: str


def request_signature(request: RoutineRequest) -> str:
    """Stable hash of everything that influences a routine (used to detect staleness)."""
    look = request.look.value if isinstance(request.look, Look) else str(request.look)
    payload = {
        "inventory": [i.to_dict() for i in request.inventory],
        "look": look,
        "preferences": request.preferences.as_conditions(),
        "features": {
            n: [f.status.value, f.value] for n, f in sorted(request.features.items())
            if n in ROUTINE_FEATURES
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _technique(step: StepDefinition, item: InventoryItem) -> tuple[str, str | None]:
    if item.formulation is not None and item.formulation.value in step.techniques:
        return step.techniques[item.formulation.value], None
    note = UNKNOWN_FORMULATION_NOTE if item.formulation is None else None
    return step.techniques["default"], note


def generate_routine(request: RoutineRequest, tutorial: TutorialRules) -> Routine:
    """Build a routine that references only items in ``request.inventory``."""
    if not request.inventory:
        raise RoutineError(
            "empty_inventory",
            "Add at least one product you own to generate a routine.",
        )
    try:
        look = Look(request.look)
    except ValueError as exc:
        raise RoutineError("invalid_look", "Please choose a look: Everyday, Office, Festive "
                           "or Glam.") from exc

    # 1. Group inventory by step; first-added item is primary, the rest are alternatives.
    by_step: dict[str, list[InventoryItem]] = {}
    for item in request.inventory:
        step = tutorial.step_for_category(item.category)
        if step is None:  # impossible with validated rules; guard anyway
            raise RoutineError("invalid_item", f"No routine step exists for {item.category}.")
        by_step.setdefault(step.step_id, []).append(item)

    skipped: list[SkippedStep] = []
    present: dict[str, list[InventoryItem]] = {}
    for step_id, items in by_step.items():
        step = tutorial.steps[step_id]
        if look not in step.looks:
            skipped.append(SkippedStep(step_id, step.title,
                                       f"Not part of the {look.value} look."))
        else:
            present[step_id] = items
    if not present:
        raise RoutineError(
            "no_applicable_steps",
            "None of your products are used in this look. Try another look or add products.",
        )

    usable = {n: f.value for n, f in request.features.items()
              if n in ROUTINE_FEATURES and f.usable and f.value}
    primary = {s: items[0] for s, items in present.items()}
    formulations = {s: item.formulation for s, item in primary.items()}

    # 2. Order.
    sequence = {s.step_id: s.sequence for s in tutorial.steps.values()}
    ordered = order_steps(
        present, sequence, tutorial.ordering,
        OrderingContext(look=look, concealer_order=request.preferences.concealer_order,
                        formulations=formulations),
    )

    # 3. Instructions.
    rule_ctx = RuleContext(look=look, present_steps=frozenset(present), features=usable,
                           preferences=request.preferences.as_conditions())
    steps: list[RoutineStep] = []
    for number, step_id in enumerate(ordered, start=1):
        step = tutorial.steps[step_id]
        item = primary[step_id]
        technique, note = _technique(step, item)
        chosen = select_rules(step_id, rule_ctx, tutorial.rules, item.formulation)
        instructions = tuple(r.instruction for r in chosen if r.kind != "feature")
        tips = tuple(r.instruction for r in chosen if r.kind == "feature")
        cautions = list(step.cautions)
        for r in chosen:
            cautions.extend(c for c in r.cautions if c not in cautions)
        compat = []
        for rule in tutorial.compatibility:
            a, b = rule.steps
            if step_id == b and a in primary and primary[a].base and item.base and \
                    (primary[a].base, item.base) == rule.bases:
                compat.append(rule.note)
        optional = look in step.optional_in_looks
        steps.append(RoutineStep(
            number=number, step_id=step_id, title=step.title, item=item, purpose=step.purpose,
            technique=technique, technique_note=note, instructions=instructions,
            feature_tips=tips, optional=optional,
            optional_reason=(f"Optional for the {look.value} look." if optional else None),
            compatibility_notes=tuple(compat), cautions=tuple(cautions),
            alternatives=tuple(present[step_id][1:]),
            applied_rule_ids=tuple(r.rule_id for r in chosen),
        ))

    # 4. Notes and suggestions.
    notes: list[str] = []
    for name, step_ids in FEATURE_STEPS.items():
        if name not in usable and any(s in present for s in step_ids):
            label = name.replace("_", " ")
            notes.append(f"Tips based on {label} were not added because your {label} is not "
                         "estimated or confirmed. You can set it on the Face Analysis or Shade "
                         "Finder page.")
    if any(len(items) > 1 for items in present.values()):
        notes.append("Where you own several products of one type, the first one you added is "
                     "used; the others are listed as alternatives.")
    suggestions = tuple(
        s.text for s in tutorial.suggestions if s.step_id not in present and look in s.looks
    )

    return Routine(
        look=look,
        look_label=tutorial.looks[look]["label"],
        steps=tuple(steps),
        skipped=tuple(skipped),
        suggestions=suggestions,
        notes=tuple(notes),
        general_cautions=tutorial.general_cautions,
        signature=request_signature(request),
    )
