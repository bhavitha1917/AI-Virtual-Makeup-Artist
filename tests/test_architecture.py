"""Structural checks: layer boundaries, no absolute paths, no network/LLM dependencies."""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re

import pytest

import src
from tests.conftest import ROOT

SRC = ROOT / "src"


def python_files(*dirs):
    for d in dirs:
        yield from (ROOT / d).rglob("*.py")


def imports_of(path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_all_modules_import():
    for mod in pkgutil.walk_packages(src.__path__, "src."):
        importlib.import_module(mod.name)


def test_streamlit_only_in_ui_layer():
    for path in SRC.rglob("*.py"):
        if "ui" in path.relative_to(SRC).parts:
            continue
        assert not any(i.startswith("streamlit") for i in imports_of(path)), path


@pytest.mark.parametrize("layer, forbidden", [
    ("core", ("src.data", "src.vision", "src.recommendation", "src.routine", "src.ui")),
    ("data", ("src.vision", "src.recommendation", "src.routine", "src.ui")),
    ("vision", ("src.recommendation", "src.routine", "src.ui", "src.data")),
    ("recommendation", ("src.vision", "src.routine", "src.ui")),
    ("routine", ("src.vision", "src.recommendation", "src.ui")),
])
def test_layer_dependencies(layer, forbidden):
    for path in (SRC / layer).rglob("*.py"):
        bad = [i for i in imports_of(path) if i.startswith(forbidden)]
        assert not bad, (path, bad)


def test_no_absolute_local_paths_in_code_or_config():
    pattern = re.compile(r"[A-Za-z]:\\\\|/Users/|/home/|C:/")
    for path in [*python_files("src", "scripts"), ROOT / "app.py",
                 ROOT / ".streamlit" / "config.toml"]:
        assert not pattern.search(path.read_text(encoding="utf-8")), path


def test_no_llm_or_paid_api_dependencies():
    reqs = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for name in ("openai", "anthropic", "langchain", "google-generativeai", "cohere"):
        assert name not in reqs


def test_only_model_asset_module_uses_network():
    for path in SRC.rglob("*.py"):
        uses_net = any(i.startswith(("urllib.request", "requests", "http.client", "socket"))
                       for i in imports_of(path))
        assert not uses_net or path.name == "model_asset.py", path


FILE_WRITE_ATTRS = {"imwrite", "write_bytes", "write_text", "tofile", "mkstemp"}


def test_no_file_io_in_vision_except_model_asset():
    """Images stay in memory: no builtin open(), cv2.imwrite, Path.write_* or temp files."""
    for path in (SRC / "vision").rglob("*.py"):
        if path.name == "model_asset.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            assert not (isinstance(func, ast.Name) and func.id == "open"), path
            assert not (isinstance(func, ast.Attribute) and func.attr in FILE_WRITE_ATTRS), path


def test_app_entry_point_is_thin():
    lines = [ln for ln in (ROOT / "app.py").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.strip().startswith(("#", '"""', "from", "import"))]
    assert len(lines) <= 12


def test_requirements_are_pinned():
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            assert "==" in line, line
