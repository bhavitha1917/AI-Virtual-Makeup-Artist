"""Dependency-aware ordering of routine steps.

Conditional constraints are evaluated against an ``OrderingContext``; the resulting graph
over *all* defined steps is checked for cycles, and order between the steps actually
present is derived from reachability so that absent intermediate steps do not drop
transitive constraints (e.g. skin prep → [primer] → foundation). Kahn's algorithm with a
(sequence, step_id) min-heap makes the result deterministic.
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from src.core.enums import ConcealerOrder, Formulation, Look
from src.core.errors import RoutineError
from src.data.schema import OrderingConstraint


@dataclass(frozen=True)
class OrderingContext:
    look: Look
    concealer_order: ConcealerOrder = ConcealerOrder.AFTER_FOUNDATION
    formulations: Mapping[str, Formulation | None] = field(default_factory=dict)


def constraint_active(constraint: OrderingConstraint, ctx: OrderingContext) -> bool:
    when = constraint.when
    if when is None:
        return True
    if "look" in when:
        return ctx.look in when["look"]
    if "concealer_order" in when:
        return ctx.concealer_order in when["concealer_order"]
    if "formulation" in when:
        step_id, forms = when["formulation"]
        return ctx.formulations.get(step_id) in forms
    return False


def build_graph(step_ids: Iterable[str], constraints: Iterable[OrderingConstraint],
                ctx: OrderingContext) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {s: set() for s in step_ids}
    for c in constraints:
        if constraint_active(c, ctx):
            if c.before not in graph or c.after not in graph:
                raise RoutineError("invalid_dependency",
                                   details=f"{c.constraint_id} references an unknown step")
            graph[c.before].add(c.after)
    return graph


def find_cycle(graph: Mapping[str, set[str]]) -> list[str] | None:
    """Return one cycle as a list of step IDs, or ``None`` if the graph is acyclic."""
    white, grey, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = grey
        stack.append(node)
        for nxt in sorted(graph[node]):
            if color[nxt] == grey:
                return stack[stack.index(nxt):] + [nxt]
            if color[nxt] == white:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return None

    for node in sorted(graph):
        if color[node] == white:
            found = visit(node)
            if found:
                return found
    return None


def _reachable(graph: Mapping[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    frontier = list(graph[start])
    while frontier:
        node = frontier.pop()
        if node not in seen:
            seen.add(node)
            frontier.extend(graph[node])
    return seen


def order_steps(present: Iterable[str], sequence: Mapping[str, int],
                constraints: Iterable[OrderingConstraint], ctx: OrderingContext) -> list[str]:
    """Order ``present`` steps so every active constraint (direct or transitive) holds."""
    present_set = set(present)
    unknown = present_set - set(sequence)
    if unknown:
        raise RoutineError("invalid_dependency", details=f"unknown steps {sorted(unknown)}")
    graph = build_graph(sequence, constraints, ctx)
    cycle = find_cycle(graph)
    if cycle:
        raise RoutineError(
            "ordering_cycle",
            "The routine rules contain contradictory ordering constraints.",
            details=" → ".join(cycle),
        )
    edges = {s: _reachable(graph, s) & present_set for s in present_set}
    indegree = dict.fromkeys(present_set, 0)
    for targets in edges.values():
        for t in targets:
            indegree[t] += 1
    heap = [(sequence[s], s) for s, d in indegree.items() if d == 0]
    heapq.heapify(heap)
    ordered: list[str] = []
    while heap:
        _, step = heapq.heappop(heap)
        ordered.append(step)
        for t in edges[step]:
            indegree[t] -= 1
            if indegree[t] == 0:
                heapq.heappush(heap, (sequence[t], t))
    return ordered


def find_any_context_cycle(
    sequence: Mapping[str, int], constraints: Iterable[OrderingConstraint]
) -> tuple[str, list[str]] | None:
    """Exhaustively check every context the constraints can distinguish for a cycle.

    Returns ``(context description, cycle)`` for the first cyclic context, else ``None``.
    """
    constraints = list(constraints)
    form_options: dict[str, set[Formulation | None]] = {}
    for c in constraints:
        if c.when and "formulation" in c.when:
            step_id, forms = c.when["formulation"]
            form_options.setdefault(step_id, {None}).update(forms)
    steps_with_forms = sorted(form_options)
    combos = itertools.product(*(sorted(form_options[s], key=lambda f: f.value if f else "")
                                 for s in steps_with_forms))
    for forms in combos:
        formulations = dict(zip(steps_with_forms, forms, strict=True))
        for look in Look:
            for order in ConcealerOrder:
                ctx = OrderingContext(look=look, concealer_order=order, formulations=formulations)
                cycle = find_cycle(build_graph(sequence, constraints, ctx))
                if cycle:
                    forms_desc = {k: (v.value if v else None) for k, v in formulations.items()}
                    desc = (f"look={look.value}, concealer_order={order.value}, "
                            f"formulations={forms_desc}")
                    return desc, cycle
    return None
