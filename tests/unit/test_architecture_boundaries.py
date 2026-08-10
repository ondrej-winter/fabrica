"""Import-boundary tests for hexagonal vertical-slice architecture."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "fabrica"
FEATURES_ROOT = SRC_ROOT / "features"


def test_feature_modules_do_not_import_product_cli_or_bootstrap() -> None:
    """Keep feature slices independent from product CLI and composition root modules."""
    forbidden_prefixes = (
        "fabrica.adapters.inbound.cli",
        "fabrica.bootstrap",
    )

    violations = _import_violations(FEATURES_ROOT, forbidden_prefixes)

    assert violations == []


def test_application_modules_do_not_import_adapters_or_bootstrap() -> None:
    """Keep application layers independent from edge adapters and composition wiring."""
    application_roots = tuple(FEATURES_ROOT.glob("*/application"))
    violations: list[str] = []
    for application_root in application_roots:
        violations.extend(
            _import_violations(
                application_root,
                (
                    "fabrica.adapters",
                    "fabrica.bootstrap",
                    ".adapters",
                ),
            ),
        )

    assert violations == []


def test_product_cli_runner_does_not_import_feature_cli_command_models() -> None:
    """Keep top-level CLI dispatch contribution-driven instead of feature-specific."""
    runner_path = SRC_ROOT / "adapters" / "inbound" / "cli" / "runner.py"
    tree = ast.parse(runner_path.read_text(encoding="utf-8"), filename=str(runner_path))

    forbidden_prefixes = (
        "fabrica.features.agent_runtime.adapters.inbound.cli",
        "fabrica.features.developer_workflow.adapters.inbound.cli",
    )

    violations = [import_name for import_name in _import_names(tree) if _is_forbidden(import_name, forbidden_prefixes)]

    assert violations == []


def _import_violations(root: Path, forbidden_prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for import_name in _import_names(tree):
            if _is_forbidden(import_name, forbidden_prefixes):
                relative_path = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}: imports {import_name}")
    return violations


def _import_names(tree: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names.append(module)
    return tuple(names)


def _is_forbidden(import_name: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(import_name == prefix or import_name.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
