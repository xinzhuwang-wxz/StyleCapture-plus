from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path

FORBIDDEN_DOMAIN_IMPORTS = frozenset(
    {
        "celery",
        "fastapi",
        "litellm",
        "pydantic",
        "redis",
        "sqlalchemy",
    }
)
FORBIDDEN_APPLICATION_IMPORTS = frozenset(
    {
        "celery",
        "fastapi",
        "litellm",
        "redis",
        "sqlalchemy",
    }
)
GENERIC_DUMPING_MODULES = frozenset({"common.py", "helpers.py", "manager.py", "utils.py"})


def imported_roots(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".", maxsplit=1)[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.split(".", maxsplit=1)[0]


def policy_for(path: Path) -> frozenset[str] | None:
    if path.name == "domain.py" or "domain" in path.parts:
        return FORBIDDEN_DOMAIN_IMPORTS
    if path.name in {"application.py", "ports.py"} or "application" in path.parts:
        return FORBIDDEN_APPLICATION_IMPORTS
    return None


def check(target: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(target.rglob("*.py")):
        relative = path.relative_to(target)
        if path.name in GENERIC_DUMPING_MODULES:
            violations.append(
                f"{relative.as_posix()} uses a generic dumping-module name; "
                "place behavior in its owning feature"
            )
        forbidden = policy_for(relative)
        if forbidden is None:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except SyntaxError as error:
            violations.append(f"{relative.as_posix()} cannot be parsed: {error.msg}")
            continue
        for module in sorted(set(imported_roots(tree)) & forbidden):
            violations.append(f"{relative.as_posix()} imports forbidden module {module}")
    return violations


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_boundaries.py <python-source-root>")
        return 2
    target = Path(argv[1]).resolve()
    if not target.is_dir():
        print(f"source root does not exist: {target}")
        return 2
    violations = check(target)
    if violations:
        print("\n".join(violations))
        return 1
    print("architecture boundaries: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
