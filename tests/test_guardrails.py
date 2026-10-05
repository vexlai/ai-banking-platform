"""Structural guardrail tests for module boundaries (README section 4).

These tests fail the build when a contributor re-introduces a layer violation:

1. ``apps/**`` never imports from ``src/`` (Guardrail 1), except the single
   sanctioned dual-mode file ``apps/demo_ui/app.py``.
2. ``src/**`` and ``api/**`` never import ``streamlit`` (forward guardrail).
3. ``contracts/**`` stays pure: stdlib plus ``pydantic`` only, never ``src/``.
4. No module re-introduces the deleted ``src.tools.schemas`` re-export shim.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = REPO_ROOT / "apps"
SRC_ROOT = REPO_ROOT / "src"
API_ROOT = REPO_ROOT / "api"
CONTRACTS_ROOT = REPO_ROOT / "contracts"
LEGACY_SCHEMAS_MODULE = "src.tools.schemas"
CONTRACTS_ALLOWED_THIRD_PARTY = frozenset({"pydantic"})
APPS_SRC_IMPORT_ALLOWLIST = frozenset({"apps/demo_ui/app.py"})
SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", "node_modules"})


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if not SKIP_DIRS.intersection(path.relative_to(REPO_ROOT).parts)
    )


def _absolute_imports(path: Path) -> list[str]:
    """Dotted names of every absolute ``import x`` / ``from x import y`` in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def _import_roots(path: Path) -> set[str]:
    return {name.split(".", maxsplit=1)[0] for name in _absolute_imports(path)}


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _stdlib_roots() -> set[str]:
    return set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def test_apps_never_import_src() -> None:
    """Guardrail 1: apps/ talks HTTP, except the sanctioned dual-mode UI file."""
    offenders = [
        _relative(path)
        for path in _python_files(APPS_ROOT)
        if "src" in _import_roots(path)
        and _relative(path) not in APPS_SRC_IMPORT_ALLOWLIST
    ]
    assert not offenders, f"apps/ must not import from src/: {offenders}"


def test_backend_never_imports_streamlit() -> None:
    """Forward guardrail: src/ and api/ stay free of the Streamlit UI."""
    offenders = [
        _relative(path)
        for root in (SRC_ROOT, API_ROOT)
        for path in _python_files(root)
        if "streamlit" in _import_roots(path)
    ]
    assert not offenders, f"src/ and api/ must not import streamlit: {offenders}"


def test_contracts_package_is_pure() -> None:
    """Guardrail 2: the shared contract depends on stdlib and pydantic only."""
    allowed = _stdlib_roots() | CONTRACTS_ALLOWED_THIRD_PARTY | {"contracts"}
    offenders = {
        _relative(path): sorted(_import_roots(path) - allowed)
        for path in _python_files(CONTRACTS_ROOT)
        if _import_roots(path) - allowed
    }
    assert not offenders, f"contracts/ must stay pure (stdlib + pydantic): {offenders}"


def test_legacy_schemas_shim_is_not_reintroduced() -> None:
    """The shim was deleted, so every consumer must import `contracts` directly."""
    offenders = [
        _relative(path)
        for path in _python_files(REPO_ROOT)
        if any(
            name == LEGACY_SCHEMAS_MODULE
            or name.startswith(f"{LEGACY_SCHEMAS_MODULE}.")
            for name in _absolute_imports(path)
        )
    ]
    assert not offenders, (
        f"`{LEGACY_SCHEMAS_MODULE}` no longer exists; import `contracts` directly: "
        f"{offenders}"
    )
