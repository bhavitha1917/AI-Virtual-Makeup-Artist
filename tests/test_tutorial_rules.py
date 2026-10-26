import copy
import json

import pytest

from src.config import DATA_DIR
from src.core.enums import Look
from src.core.errors import CatalogError, RoutineError
from src.data.schema import OrderingConstraint, parse_tutorial_rules
from src.routine.application_order import OrderingContext, order_steps
from src.routine.rule_engine import feature_tips, find_contradictions, validate_rules


@pytest.fixture
def raw():
    return copy.deepcopy(json.loads((DATA_DIR / "tutorial_rules.json").read_text("utf-8")))


def parse_issues(raw):
    with pytest.raises(CatalogError) as exc:
        validate_rules(parse_tutorial_rules(raw))
    return exc.value.issues


def test_production_rules_valid(production_rules):
    assert len(production_rules.steps) == 16
    assert not find_contradictions(production_rules.rules)


def test_duplicate_rule_id(raw):
    raw["rules"].append(dict(raw["rules"][0]))
    assert any("duplicate rule id" in i for i in parse_issues(raw))


def test_unknown_step_reference(raw):
    raw["rules"][0]["step_id"] = "contour"
    raw["ordering"][0]["after"] = "contour"
    issues = parse_issues(raw)
    assert sum("unknown step 'contour'" in i for i in issues) == 2


def test_invalid_requires_dependency(raw):
    raw["rules"][0]["requires_steps"] = ["nonexistent"]
    assert any("unknown step 'nonexistent'" in i for i in parse_issues(raw))


def test_contradictory_rules_detected(raw):
    clone = dict(raw["rules"][0])  # R-FND-LIGHT: group foundation_look, priority 40
    clone["rule_id"] = "R-FND-CONFLICT"
    clone["instruction"] = "Apply a thick layer everywhere."
    raw["rules"].append(clone)
    assert any("contradict" in i for i in parse_issues(raw))


def test_disjoint_conditions_are_not_contradictions(production_rules):
    groups = [r for r in production_rules.rules if r.exclusive_group == "blush_placement"]
    assert len(groups) == 5 and not find_contradictions(tuple(groups))


def test_ordering_cycle_detected(raw):
    raw["ordering"].append({"constraint_id": "O-999", "before": "setting_spray",
                            "after": "skin_prep", "when": None, "rationale": "bad"})
    assert any("ordering cycle" in i for i in parse_issues(raw))


def test_conditional_cycle_detected_exhaustively(raw):
    # Only cyclic when blush is a powder: powder → blush (O-015) plus blush → powder.
    raw["ordering"].append({"constraint_id": "O-998", "before": "blush", "after": "powder",
                            "when": {"formulation": {"blush": ["powder"]}}, "rationale": "bad"})
    assert any("ordering cycle" in i and "blush" in i for i in parse_issues(raw))


def test_runtime_cycle_raises_routine_error():
    seq = {"a": 1, "b": 2}
    cons = [OrderingConstraint("1", "a", "b", None, ""),
            OrderingConstraint("2", "b", "a", None, "")]
    with pytest.raises(RoutineError) as exc:
        order_steps(["a", "b"], seq, cons, OrderingContext(look=Look.EVERYDAY))
    assert exc.value.code == "ordering_cycle"


def test_transitive_constraint_survives_absent_middle_step():
    # a → b → c, but the sequence hint alone would put c first; b is not present.
    seq = {"a": 3, "b": 2, "c": 1}
    cons = [OrderingConstraint("1", "a", "b", None, ""),
            OrderingConstraint("2", "b", "c", None, "")]
    assert order_steps(["a", "c"], seq, cons, OrderingContext(look=Look.EVERYDAY)) == ["a", "c"]
    assert order_steps(["c", "a"], seq, [], OrderingContext(look=Look.EVERYDAY)) == ["c", "a"]


def test_unknown_present_step_rejected():
    with pytest.raises(RoutineError):
        order_steps(["zzz"], {"a": 1}, [], OrderingContext(look=Look.EVERYDAY))


def test_missing_look_and_step_detected(raw):
    del raw["looks"]["glam"]
    raw["steps"] = [s for s in raw["steps"] if s["step_id"] != "mascara"]
    raw["rules"] = [r for r in raw["rules"] if r["step_id"] != "mascara"]
    raw["ordering"] = [o for o in raw["ordering"] if "mascara" not in (o["before"], o["after"])]
    raw["suggestions"] = [s for s in raw["suggestions"] if s["step_id"] != "mascara"]
    issues = parse_issues(raw)
    assert any("missing look 'glam'" in i for i in issues)
    assert any("no step defined for category 'mascara'" in i for i in issues)


def test_techniques_require_default(raw):
    del raw["steps"][0]["techniques"]["default"]
    assert any("techniques" in i for i in parse_issues(raw))


def test_feature_tips_for_shade_finder(production_rules):
    tips = feature_tips("eyeliner", {"eye_shape": "hooded", "eye_tilt": "downturned"},
                        production_rules)
    assert len(tips) == 2 and any("hooded" in t for t in tips)
    assert feature_tips("eyeliner", {}, production_rules) == []
