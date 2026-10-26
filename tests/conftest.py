from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_docs() -> tuple[dict, dict]:
    """Fictional test catalog (never the production catalog)."""
    products = json.loads((FIXTURES / "products.json").read_text(encoding="utf-8"))
    shades = json.loads((FIXTURES / "shades.json").read_text(encoding="utf-8"))
    return products, shades


@pytest.fixture
def docs(fixture_docs):
    return copy.deepcopy(fixture_docs[0]), copy.deepcopy(fixture_docs[1])


@pytest.fixture(scope="session")
def test_catalog(fixture_docs):
    from src.data.schema import parse_catalog

    return parse_catalog(*fixture_docs)


@pytest.fixture(scope="session")
def production_rules():
    from src.routine.rule_engine import load_validated_rules

    return load_validated_rules()


@pytest.fixture(scope="session")
def model_path():
    from src.config import SETTINGS

    path = SETTINGS.model.path
    if not path.is_file():
        pytest.skip(f"MediaPipe model not present at {path}; run scripts/download_model.py")
    return path
