"""Schema validation for the product knowledge base and tutorial rules.

Validators collect every issue (with a field path) and raise one ``CatalogError``
so that data authors can fix all problems in one pass.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.core.enums import (
    Base,
    Category,
    ColorFamily,
    ConcealerOrder,
    CorrectionTarget,
    Coverage,
    Depth,
    EyeShape,
    EyeTilt,
    FaceShape,
    Finish,
    Formulation,
    Intensity,
    Look,
    Undertone,
    VerificationStatus,
    enum_values,
)
from src.core.errors import CatalogError

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
RULE_ID_PATTERN = re.compile(r"^[A-Z]-[A-Z0-9-]{2,40}$")


# --------------------------------------------------------------------------- models
@dataclass(frozen=True)
class Product:
    product_id: str
    brand: str
    product_name: str
    category: Category
    finish: Finish | None
    coverage: Coverage | None
    formulation: Formulation | None
    base: Base | None
    intended_use: tuple[str, ...]
    price: float | None
    currency: str | None
    product_url: str | None
    source: str
    verification_status: VerificationStatus
    shade_ids: tuple[str, ...]

    @property
    def display_name(self) -> str:
        return f"{self.brand} {self.product_name}"


@dataclass(frozen=True)
class Shade:
    shade_id: str
    product_id: str
    shade_name: str
    depth: Depth | None
    undertone: Undertone | None
    color_family: ColorFamily | None
    intensity: Intensity | None
    finish: Finish | None
    correction_target: CorrectionTarget | None
    suitable_depths: tuple[Depth, ...]
    suitable_looks: tuple[Look, ...]
    illustrative_swatch_hex: str | None
    source: str
    verification_status: VerificationStatus


@dataclass(frozen=True)
class Catalog:
    products: Mapping[str, Product]
    shades: Mapping[str, Shade]
    catalog_type: str
    notice: str

    def products_in(self, category: Category) -> list[Product]:
        return sorted(
            (p for p in self.products.values() if p.category is category),
            key=lambda p: p.product_id,
        )

    def shades_for(self, product: Product) -> list[Shade]:
        return [self.shades[sid] for sid in product.shade_ids]

    @property
    def is_demo(self) -> bool:
        return self.catalog_type == "demonstration"


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    category: Category
    title: str
    purpose: str
    sequence: int
    looks: frozenset[Look]
    optional_in_looks: frozenset[Look]
    techniques: Mapping[str, str]
    cautions: tuple[str, ...]


@dataclass(frozen=True)
class TutorialRule:
    rule_id: str
    step_id: str
    kind: str
    looks: frozenset[Look] | None
    conditions: Mapping[str, frozenset[str]]
    requires_steps: tuple[str, ...]
    instruction: str
    priority: int
    exclusive_group: str | None
    optional: bool
    cautions: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class OrderingConstraint:
    constraint_id: str
    before: str
    after: str
    when: Mapping[str, Any] | None
    rationale: str


@dataclass(frozen=True)
class CompatibilityRule:
    compat_id: str
    steps: tuple[str, str]
    bases: tuple[Base, Base]
    note: str


@dataclass(frozen=True)
class Suggestion:
    suggestion_id: str
    step_id: str
    looks: frozenset[Look]
    text: str


@dataclass(frozen=True)
class TutorialRules:
    looks: Mapping[Look, Mapping[str, str]]
    steps: Mapping[str, StepDefinition]
    rules: tuple[TutorialRule, ...]
    ordering: tuple[OrderingConstraint, ...]
    compatibility: tuple[CompatibilityRule, ...]
    suggestions: tuple[Suggestion, ...]
    general_cautions: tuple[str, ...] = field(default=())

    def step_for_category(self, category: Category) -> StepDefinition | None:
        for step in self.steps.values():
            if step.category is category:
                return step
        return None


# --------------------------------------------------------------------------- helpers
class _Issues:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, path: str, message: str) -> None:
        self.items.append(f"{path}: {message}")

    def raise_if_any(self) -> None:
        if self.items:
            raise CatalogError(self.items)


def _enum(issues: _Issues, path: str, value: Any, enum_cls: type, nullable: bool = True) -> Any:
    if value is None:
        if not nullable:
            issues.add(path, "is required")
        return None
    try:
        return enum_cls(value)
    except ValueError:
        issues.add(path, f"invalid value {value!r}; allowed: {', '.join(enum_values(enum_cls))}")
        return None


def _enum_list(issues: _Issues, path: str, values: Any, enum_cls: type) -> tuple:
    if values is None:
        return ()
    if not isinstance(values, list):
        issues.add(path, "must be a list")
        return ()
    out = []
    for i, v in enumerate(values):
        member = _enum(issues, f"{path}[{i}]", v, enum_cls, nullable=False)
        if member is not None:
            out.append(member)
    return tuple(out)


def _text(issues: _Issues, path: str, value: Any, max_len: int = 200, required: bool = True) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            issues.add(path, "is required")
        return ""
    if not isinstance(value, str):
        issues.add(path, "must be a string")
        return ""
    if len(value) > max_len:
        issues.add(path, f"longer than {max_len} characters")
    return value.strip()


def _require_keys(issues: _Issues, path: str, row: Any, keys: Iterable[str]) -> bool:
    if not isinstance(row, dict):
        issues.add(path, "must be an object")
        return False
    missing = [k for k in keys if k not in row]
    for k in missing:
        issues.add(f"{path}.{k}", "missing required field")
    return not missing


def _rows(issues: _Issues, raw: Any, key: str) -> list:
    if not isinstance(raw, dict):
        issues.add(key, "top-level document must be an object")
        return []
    rows = raw.get(key)
    if not isinstance(rows, list):
        issues.add(key, "must be a list")
        return []
    return rows


PRODUCT_KEYS = (
    "product_id", "brand", "product_name", "category", "finish", "coverage", "formulation",
    "base", "intended_use", "price", "currency", "product_url", "source",
    "verification_status", "shade_ids",
)
SHADE_KEYS = (
    "shade_id", "product_id", "shade_name", "depth", "undertone", "color_family", "intensity",
    "finish", "correction_target", "suitable_depths", "suitable_looks",
    "illustrative_swatch_hex", "source", "verification_status",
)


# --------------------------------------------------------------------------- catalog
def parse_catalog(raw_products: Any, raw_shades: Any) -> Catalog:
    """Validate raw product and shade documents and return an immutable ``Catalog``."""
    issues = _Issues()
    products: dict[str, Product] = {}
    shades: dict[str, Shade] = {}

    for i, row in enumerate(_rows(issues, raw_products, "products")):
        path = f"products[{i}]"
        if not _require_keys(issues, path, row, PRODUCT_KEYS):
            continue
        pid = row["product_id"]
        if not isinstance(pid, str) or not ID_PATTERN.match(pid):
            issues.add(f"{path}.product_id", f"invalid id {pid!r}")
            continue
        if pid in products:
            issues.add(f"{path}.product_id", f"duplicate product id {pid!r}")
            continue
        status = _enum(issues, f"{path}.verification_status", row["verification_status"],
                       VerificationStatus, nullable=False)
        price, currency, url = row["price"], row["currency"], row["product_url"]
        if status is not VerificationStatus.VERIFIED and any(
            v is not None for v in (price, currency, url)
        ):
            issues.add(path, "price, currency and product_url must be null unless verified")
        if price is not None and (not isinstance(price, int | float) or price < 0):
            issues.add(f"{path}.price", "must be a non-negative number")
        if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
            issues.add(f"{path}.product_url", "must be an https URL")
        shade_ids = row["shade_ids"]
        if not isinstance(shade_ids, list) or not all(isinstance(s, str) for s in shade_ids):
            issues.add(f"{path}.shade_ids", "must be a list of strings")
            shade_ids = []
        uses = row["intended_use"]
        if not isinstance(uses, list) or not all(isinstance(u, str) for u in uses):
            issues.add(f"{path}.intended_use", "must be a list of strings")
            uses = []
        products[pid] = Product(
            product_id=pid,
            brand=_text(issues, f"{path}.brand", row["brand"], 80),
            product_name=_text(issues, f"{path}.product_name", row["product_name"], 80),
            category=_enum(issues, f"{path}.category", row["category"], Category, nullable=False),
            finish=_enum(issues, f"{path}.finish", row["finish"], Finish),
            coverage=_enum(issues, f"{path}.coverage", row["coverage"], Coverage),
            formulation=_enum(issues, f"{path}.formulation", row["formulation"], Formulation),
            base=_enum(issues, f"{path}.base", row["base"], Base),
            intended_use=tuple(uses),
            price=price,
            currency=currency,
            product_url=url,
            source=_text(issues, f"{path}.source", row["source"], 300),
            verification_status=status,
            shade_ids=tuple(shade_ids),
        )

    for i, row in enumerate(_rows(issues, raw_shades, "shades")):
        path = f"shades[{i}]"
        if not _require_keys(issues, path, row, SHADE_KEYS):
            continue
        sid = row["shade_id"]
        if not isinstance(sid, str) or not ID_PATTERN.match(sid):
            issues.add(f"{path}.shade_id", f"invalid id {sid!r}")
            continue
        if sid in shades:
            issues.add(f"{path}.shade_id", f"duplicate shade id {sid!r}")
            continue
        status = _enum(issues, f"{path}.verification_status", row["verification_status"],
                       VerificationStatus, nullable=False)
        swatch = row["illustrative_swatch_hex"]
        if swatch is not None:
            if status is not VerificationStatus.DEMO:
                issues.add(f"{path}.illustrative_swatch_hex", "only allowed for demo shades")
            elif not isinstance(swatch, str) or not HEX_PATTERN.match(swatch):
                issues.add(f"{path}.illustrative_swatch_hex", f"invalid hex {swatch!r}")
        shades[sid] = Shade(
            shade_id=sid,
            product_id=str(row["product_id"]),
            shade_name=_text(issues, f"{path}.shade_name", row["shade_name"], 80),
            depth=_enum(issues, f"{path}.depth", row["depth"], Depth),
            undertone=_enum(issues, f"{path}.undertone", row["undertone"], Undertone),
            color_family=_enum(issues, f"{path}.color_family", row["color_family"], ColorFamily),
            intensity=_enum(issues, f"{path}.intensity", row["intensity"], Intensity),
            finish=_enum(issues, f"{path}.finish", row["finish"], Finish),
            correction_target=_enum(
                issues, f"{path}.correction_target", row["correction_target"], CorrectionTarget
            ),
            suitable_depths=_enum_list(issues, f"{path}.suitable_depths",
                                       row["suitable_depths"], Depth),
            suitable_looks=_enum_list(issues, f"{path}.suitable_looks",
                                      row["suitable_looks"], Look),
            illustrative_swatch_hex=swatch,
            source=_text(issues, f"{path}.source", row["source"], 300),
            verification_status=status,
        )

    # Cross-references in both directions.
    for pid, product in products.items():
        for sid in product.shade_ids:
            shade = shades.get(sid)
            if shade is None:
                issues.add(f"product {pid}", f"references missing shade {sid!r}")
            elif shade.product_id != pid:
                issues.add(f"product {pid}", f"shade {sid!r} belongs to {shade.product_id!r}")
    for sid, shade in shades.items():
        product = products.get(shade.product_id)
        if product is None:
            issues.add(f"shade {sid}", f"references missing product {shade.product_id!r}")
            continue
        if sid not in product.shade_ids:
            issues.add(f"shade {sid}", f"not listed in product {product.product_id!r} shade_ids")
        confirmed = shade.verification_status in (VerificationStatus.VERIFIED,
                                                  VerificationStatus.DEMO)
        if product.category in (Category.FOUNDATION, Category.CONCEALER) and confirmed \
                and shade.depth is None:
            issues.add(f"shade {sid}", "complexion shades must list a depth")
        if product.category is Category.COLOR_CORRECTOR and shade.correction_target is None:
            issues.add(f"shade {sid}", "color-corrector shades must list a correction_target")

    issues.raise_if_any()
    catalog_type = raw_products.get("catalog_type", "") if isinstance(raw_products, dict) else ""
    notice = raw_products.get("notice", "") if isinstance(raw_products, dict) else ""
    return Catalog(products=products, shades=shades, catalog_type=str(catalog_type),
                   notice=str(notice))


# --------------------------------------------------------------------------- tutorial rules
CONDITION_ENUMS: Mapping[str, type] = {
    "face_shape": FaceShape,
    "eye_shape": EyeShape,
    "eye_tilt": EyeTilt,
    "formulation": Formulation,
    "coverage": Coverage,
    "intensity": Intensity,
    "concealer_order": ConcealerOrder,
}
RULE_KINDS = frozenset({"look", "feature", "preference"})


def _parse_when(issues: _Issues, path: str, when: Any, step_ids: set[str]) -> Mapping | None:
    if when is None:
        return None
    if not isinstance(when, dict) or len(when) != 1:
        issues.add(path, "must be null or an object with exactly one key")
        return None
    (key, value), = when.items()
    if key == "look":
        return {"look": frozenset(_enum_list(issues, f"{path}.look", value, Look))}
    if key == "concealer_order":
        return {"concealer_order": frozenset(
            _enum_list(issues, f"{path}.concealer_order", value, ConcealerOrder))}
    if key == "formulation":
        if not isinstance(value, dict) or len(value) != 1:
            issues.add(f"{path}.formulation", "must map exactly one step_id to formulations")
            return None
        (step_id, forms), = value.items()
        if step_id not in step_ids:
            issues.add(f"{path}.formulation", f"unknown step {step_id!r}")
        return {"formulation": (step_id, frozenset(
            _enum_list(issues, f"{path}.formulation.{step_id}", forms, Formulation)))}
    issues.add(path, f"unknown condition key {key!r}")
    return None


def parse_tutorial_rules(raw: Any) -> TutorialRules:
    """Validate the tutorial-rules document. Contradiction/cycle checks live in the routine
    engine (``rule_engine.validate_rules``), which is invoked by the loader."""
    issues = _Issues()
    if not isinstance(raw, dict):
        raise CatalogError(["tutorial_rules: top-level document must be an object"])

    looks: dict[Look, Mapping[str, str]] = {}
    for key, meta in (raw.get("looks") or {}).items():
        look = _enum(issues, f"looks.{key}", key, Look, nullable=False)
        if look is not None and isinstance(meta, dict):
            looks[look] = {"label": _text(issues, f"looks.{key}.label", meta.get("label")),
                           "description": _text(issues, f"looks.{key}.description",
                                                meta.get("description"), 300)}
    missing_looks = set(Look) - set(looks)
    for look in sorted(missing_looks, key=lambda x: x.value):
        issues.add("looks", f"missing look {look.value!r}")

    steps: dict[str, StepDefinition] = {}
    categories_seen: set[Category] = set()
    step_keys = ("step_id", "category", "title", "purpose", "sequence", "looks",
                 "optional_in_looks", "techniques", "cautions")
    for i, row in enumerate(raw.get("steps") or []):
        path = f"steps[{i}]"
        if not _require_keys(issues, path, row, step_keys):
            continue
        sid = row["step_id"]
        if sid in steps:
            issues.add(f"{path}.step_id", f"duplicate step id {sid!r}")
            continue
        category = _enum(issues, f"{path}.category", row["category"], Category, nullable=False)
        if category in categories_seen:
            issues.add(f"{path}.category", f"category {category.value!r} has two steps")
        categories_seen.add(category)
        techniques = row["techniques"]
        if not isinstance(techniques, dict) or "default" not in techniques:
            issues.add(f"{path}.techniques", "must be an object containing 'default'")
            techniques = {"default": ""}
        for form in techniques:
            if form != "default":
                _enum(issues, f"{path}.techniques.{form}", form, Formulation, nullable=False)
        if not isinstance(row["sequence"], int):
            issues.add(f"{path}.sequence", "must be an integer")
        steps[sid] = StepDefinition(
            step_id=sid,
            category=category,
            title=_text(issues, f"{path}.title", row["title"], 80),
            purpose=_text(issues, f"{path}.purpose", row["purpose"], 300),
            sequence=int(row["sequence"]) if isinstance(row["sequence"], int) else 0,
            looks=frozenset(_enum_list(issues, f"{path}.looks", row["looks"], Look)),
            optional_in_looks=frozenset(
                _enum_list(issues, f"{path}.optional_in_looks", row["optional_in_looks"], Look)),
            techniques=dict(techniques),
            cautions=tuple(row["cautions"] or ()),
        )
    for category in Category:
        if category not in categories_seen:
            issues.add("steps", f"no step defined for category {category.value!r}")
    step_ids = set(steps)

    rules: list[TutorialRule] = []
    seen_rules: set[str] = set()
    rule_keys = ("rule_id", "step_id", "kind", "looks", "conditions", "requires_steps",
                 "instruction", "priority", "exclusive_group", "optional", "cautions",
                 "rationale")
    for i, row in enumerate(raw.get("rules") or []):
        path = f"rules[{i}]"
        if not _require_keys(issues, path, row, rule_keys):
            continue
        rid = row["rule_id"]
        if not isinstance(rid, str) or not RULE_ID_PATTERN.match(rid):
            issues.add(f"{path}.rule_id", f"invalid rule id {rid!r}")
        if rid in seen_rules:
            issues.add(f"{path}.rule_id", f"duplicate rule id {rid!r}")
            continue
        seen_rules.add(rid)
        if row["step_id"] not in step_ids:
            issues.add(f"{path}.step_id", f"unknown step {row['step_id']!r}")
        for dep in row["requires_steps"] or []:
            if dep not in step_ids:
                issues.add(f"{path}.requires_steps", f"unknown step {dep!r}")
        if row["kind"] not in RULE_KINDS:
            issues.add(f"{path}.kind", f"invalid kind {row['kind']!r}")
        conditions: dict[str, frozenset[str]] = {}
        for key, values in (row["conditions"] or {}).items():
            enum_cls = CONDITION_ENUMS.get(key)
            if enum_cls is None:
                issues.add(f"{path}.conditions", f"unknown condition {key!r}")
                continue
            conditions[key] = frozenset(
                v.value for v in _enum_list(issues, f"{path}.conditions.{key}", values, enum_cls))
        if not isinstance(row["priority"], int):
            issues.add(f"{path}.priority", "must be an integer")
        looks_value = row["looks"]
        rules.append(TutorialRule(
            rule_id=rid,
            step_id=row["step_id"],
            kind=row["kind"],
            looks=None if looks_value is None else frozenset(
                _enum_list(issues, f"{path}.looks", looks_value, Look)),
            conditions=conditions,
            requires_steps=tuple(row["requires_steps"] or ()),
            instruction=_text(issues, f"{path}.instruction", row["instruction"], 400),
            priority=int(row["priority"]) if isinstance(row["priority"], int) else 0,
            exclusive_group=row["exclusive_group"],
            optional=bool(row["optional"]),
            cautions=tuple(row["cautions"] or ()),
            rationale=_text(issues, f"{path}.rationale", row["rationale"], 300),
        ))

    ordering: list[OrderingConstraint] = []
    seen_constraints: set[str] = set()
    for i, row in enumerate(raw.get("ordering") or []):
        path = f"ordering[{i}]"
        if not _require_keys(issues, path, row, ("constraint_id", "before", "after", "when",
                                                 "rationale")):
            continue
        cid = row["constraint_id"]
        if cid in seen_constraints:
            issues.add(f"{path}.constraint_id", f"duplicate constraint id {cid!r}")
            continue
        seen_constraints.add(cid)
        for end in ("before", "after"):
            if row[end] not in step_ids:
                issues.add(f"{path}.{end}", f"unknown step {row[end]!r}")
        if row["before"] == row["after"]:
            issues.add(path, "a step cannot be ordered before itself")
        ordering.append(OrderingConstraint(
            constraint_id=cid, before=row["before"], after=row["after"],
            when=_parse_when(issues, f"{path}.when", row["when"], step_ids),
            rationale=_text(issues, f"{path}.rationale", row["rationale"], 300),
        ))

    compatibility: list[CompatibilityRule] = []
    for i, row in enumerate(raw.get("compatibility") or []):
        path = f"compatibility[{i}]"
        if not _require_keys(issues, path, row, ("compat_id", "steps", "bases", "note")):
            continue
        steps_pair, bases_pair = row["steps"], row["bases"]
        if not (isinstance(steps_pair, list) and len(steps_pair) == 2):
            issues.add(f"{path}.steps", "must list exactly two steps")
            continue
        for s in steps_pair:
            if s not in step_ids:
                issues.add(f"{path}.steps", f"unknown step {s!r}")
        bases = _enum_list(issues, f"{path}.bases", bases_pair, Base)
        if len(bases) != 2:
            issues.add(f"{path}.bases", "must list exactly two bases")
            continue
        compatibility.append(CompatibilityRule(
            compat_id=row["compat_id"], steps=(steps_pair[0], steps_pair[1]),
            bases=(bases[0], bases[1]), note=_text(issues, f"{path}.note", row["note"], 400)))

    suggestions: list[Suggestion] = []
    for i, row in enumerate(raw.get("suggestions") or []):
        path = f"suggestions[{i}]"
        if not _require_keys(issues, path, row, ("suggestion_id", "step_id", "looks", "text")):
            continue
        if row["step_id"] not in step_ids:
            issues.add(f"{path}.step_id", f"unknown step {row['step_id']!r}")
        suggestions.append(Suggestion(
            suggestion_id=row["suggestion_id"], step_id=row["step_id"],
            looks=frozenset(_enum_list(issues, f"{path}.looks", row["looks"], Look)),
            text=_text(issues, f"{path}.text", row["text"], 300)))

    issues.raise_if_any()
    return TutorialRules(
        looks=looks, steps=steps, rules=tuple(rules), ordering=tuple(ordering),
        compatibility=tuple(compatibility), suggestions=tuple(suggestions),
        general_cautions=tuple(raw.get("general_cautions") or ()),
    )
