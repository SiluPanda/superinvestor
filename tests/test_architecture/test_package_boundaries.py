from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src" / "superinvestor"
ARCHITECTURE_NOTE = ROOT / "docs" / "architecture.md"

_ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    "models": {"models"},
    "config": {"config", "models"},
    "data": {"data", "models"},
    "store": {"store", "models"},
    "mcp": {"mcp"},
}

_REQUIRED_NOTE_PHRASES = (
    "Package ownership",
    "Import boundary rules",
    "models",
    "config",
    "data",
    "store",
    "agents",
    "engine",
    "tui",
    "web",
    "mcp",
)


def _module_owner(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT)
    return relative.parts[0].replace(".py", "")


def _internal_dependencies(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    dependencies: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "superinvestor":
                continue
            if node.module.startswith("superinvestor."):
                dependency = node.module.split(".", 2)[1]
                dependencies.add(dependency)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("superinvestor."):
                    dependency = alias.name.split(".", 2)[1]
                    dependencies.add(dependency)

    return dependencies


def test_architecture_note_exists_and_covers_core_packages() -> None:
    text = ARCHITECTURE_NOTE.read_text()

    for phrase in _REQUIRED_NOTE_PHRASES:
        assert phrase in text



def test_foundational_package_boundaries() -> None:
    violations: list[str] = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        owner = _module_owner(path)
        allowed = _ALLOWED_DEPENDENCIES.get(owner)
        if allowed is None:
            continue

        dependencies = _internal_dependencies(path)
        disallowed = sorted(dep for dep in dependencies if dep not in allowed)
        if disallowed:
            violations.append(
                f"{path.relative_to(ROOT)} ({owner}) imports disallowed internal packages: "
                f"{', '.join(disallowed)}"
            )

    assert not violations, "\n".join(violations)
