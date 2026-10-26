"""Safe loading of the JSON knowledge base from project-relative paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.core.errors import CatalogError
from src.data.schema import Catalog, TutorialRules, parse_catalog, parse_tutorial_rules

PRODUCTS_FILE = "products.json"
SHADES_FILE = "shades.json"
RULES_FILE = "tutorial_rules.json"
MAX_DATA_FILE_BYTES = 5 * 1024 * 1024


def read_json(path: Path) -> Any:
    """Read a JSON file, converting I/O and syntax problems into ``CatalogError``."""
    try:
        if path.stat().st_size > MAX_DATA_FILE_BYTES:
            raise CatalogError([f"{path.name}: file is larger than {MAX_DATA_FILE_BYTES} bytes"])
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise CatalogError([f"{path.name}: file not found"]) from exc
    except json.JSONDecodeError as exc:
        raise CatalogError([f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}"]) from exc


def load_catalog(data_dir: Path = DATA_DIR) -> Catalog:
    return parse_catalog(read_json(data_dir / PRODUCTS_FILE), read_json(data_dir / SHADES_FILE))


def load_tutorial_rules(data_dir: Path = DATA_DIR) -> TutorialRules:
    """Parse and schema-validate tutorial rules.

    Semantic checks (contradictions, ordering cycles) belong to the routine engine; use
    ``src.routine.rule_engine.load_validated_rules`` to get fully validated rules.
    """
    return parse_tutorial_rules(read_json(data_dir / RULES_FILE))
