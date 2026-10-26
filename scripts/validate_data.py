"""Validate the knowledge base (products, shades, tutorial rules).

Usage:  python scripts/validate_data.py
Exit code 0 when valid; 1 with every issue listed otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.errors import CatalogError  # noqa: E402
from src.data.loader import load_catalog  # noqa: E402
from src.routine.rule_engine import load_validated_rules  # noqa: E402


def main() -> int:
    failed = False
    try:
        catalog = load_catalog()
        print(f"Catalog OK ({catalog.catalog_type}): {len(catalog.products)} products, "
              f"{len(catalog.shades)} shades")
    except CatalogError as exc:
        failed = True
        print("Catalog INVALID:", *exc.issues, sep="\n  - ")
    try:
        rules = load_validated_rules()
        print(f"Tutorial rules OK: {len(rules.steps)} steps, {len(rules.rules)} rules, "
              f"{len(rules.ordering)} ordering constraints (no contradictions, no cycles)")
    except CatalogError as exc:
        failed = True
        print("Tutorial rules INVALID:", *exc.issues, sep="\n  - ")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
