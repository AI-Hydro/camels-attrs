"""
Layering contract — camels-attrs must be standalone.

camels-attrs is the CONUS reference implementation (71 CAMELS attributes,
671 USGS gauges). aihydro-lsh depends DOWN on it for parity validation
("camels-attrs CONUS = the reference implementation" per
MCP/docs/ARCHITECTURE.md). camels-attrs has one legitimate downward
dependency of its own — pygeoglim, for CONUS geology attributes (see
geology.py, declared in [project.dependencies] as pygeoglim>=1.1.0) — but
must never import the ai_hydro tools/domain layer or any sibling data/recipe
package; that would make the reference implementation depend on the thing
it's meant to validate.

Runs offline with zero extra dependencies (uses ``ast``). import-linter
(configured in pyproject.toml) gives the same guarantee when installed; this
test is the always-on floor.
"""
from __future__ import annotations

import ast
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent / "camels_attrs"
_FORBIDDEN = {
    "ai_hydro", "aihydro_data", "aihydro_watershed",
    "aihydro_lsh", "aihydro_tools",
}


def _python_files() -> list[Path]:
    return sorted(_PKG_ROOT.rglob("*.py"))


def _forbidden_imports(tree: ast.AST) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _FORBIDDEN:
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _FORBIDDEN:
                bad.append(node.module)
    return bad


def test_camels_attrs_imports_no_sibling_package():
    """camels-attrs may depend DOWN on pygeoglim only — no other sibling import."""
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        bad = _forbidden_imports(tree)
        if bad:
            offenders[str(path.relative_to(_PKG_ROOT))] = bad

    assert not offenders, (
        "camels-attrs may only depend on pygeoglim among AI-Hydro packages, "
        "but found forbidden imports:\n"
        + "\n".join(f"  {f}: {mods}" for f, mods in offenders.items())
    )
