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
FEATURE_ROOT_LAYERS = {
    "application.py": "application",
    "domain.py": "domain",
    "ports.py": "application",
    "processing.py": "application",
    "taxonomy.py": "domain",
}
IOS_FORBIDDEN_SHELL_NAMES = (
    "AppRouter",
    "AppEnvironment",
    "ViewModel",
    "DIContainer",
    "EffectRunner",
    "OutboxScheduler",
)
IOS_FEATURE_FORBIDDEN_IMPORTS = frozenset(
    {
        "GRDB",
        "Nuke",
        "StoreKit",
        "StyleCaptureAPI",
    }
)


def imported_roots(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".", maxsplit=1)[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.split(".", maxsplit=1)[0]


def imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def policy_for(path: Path) -> frozenset[str] | None:
    if path.name == "domain.py" or "domain" in path.parts:
        return FORBIDDEN_DOMAIN_IMPORTS
    if path.name in {"application.py", "ports.py", "processing.py"} or "application" in path.parts:
        return FORBIDDEN_APPLICATION_IMPORTS
    return None


def feature_and_layer(path: Path) -> tuple[str, str] | None:
    if "features" not in path.parts:
        return None
    feature_index = path.parts.index("features")
    if len(path.parts) <= feature_index + 2:
        return None
    feature = path.parts[feature_index + 1]
    layer_part = path.parts[feature_index + 2]
    layer = FEATURE_ROOT_LAYERS.get(layer_part, layer_part)
    return feature, layer


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
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except SyntaxError as error:
            violations.append(f"{relative.as_posix()} cannot be parsed: {error.msg}")
            continue
        if forbidden is not None:
            for module in sorted(set(imported_roots(tree)) & forbidden):
                violations.append(f"{relative.as_posix()} imports forbidden module {module}")
        local_context = feature_and_layer(relative)
        if local_context is None:
            continue
        feature, local_layer = local_context
        for module in sorted(set(imported_modules(tree))):
            module_parts = module.split(".")
            if "features" not in module_parts:
                continue
            imported_feature_index = module_parts.index("features")
            if len(module_parts) <= imported_feature_index + 2:
                continue
            imported_feature = module_parts[imported_feature_index + 1]
            imported_layer_part = module_parts[imported_feature_index + 2]
            imported_layer = FEATURE_ROOT_LAYERS.get(imported_layer_part, imported_layer_part)
            if (
                local_layer in {"application", "domain"}
                and imported_layer
                in {
                    "infrastructure",
                    "interfaces",
                }
            ) or (local_layer == "interfaces" and imported_layer == "infrastructure"):
                violations.append(f"{relative.as_posix()} imports inward-forbidden layer {module}")
            elif local_layer == "infrastructure" and imported_layer == "interfaces":
                violations.append(f"{relative.as_posix()} imports outward interface layer {module}")
            if (
                imported_feature != feature
                and local_layer == "application"
                and imported_layer in {"application", "infrastructure", "interfaces"}
            ):
                violations.append(
                    f"{relative.as_posix()} couples application layers across features via {module}"
                )
    return violations


def imported_swift_modules(source: str) -> Iterable[str]:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("@testable import "):
            yield stripped.removeprefix("@testable import ").split()[0]
        elif stripped.startswith("import "):
            yield stripped.removeprefix("import ").split()[0]


def check_ios_boundaries(repository_root: Path) -> list[str]:
    app_root = repository_root / "apps" / "ios" / "StyleCaptureJourney"
    if not app_root.exists():
        return []
    violations: list[str] = []
    for path in sorted(app_root.rglob("*.swift")):
        relative = path.relative_to(repository_root)
        source = path.read_text(encoding="utf-8")
        stem = path.stem
        if any(forbidden in stem for forbidden in IOS_FORBIDDEN_SHELL_NAMES):
            violations.append(f"{relative.as_posix()} uses forbidden iOS shell naming")
        modules = set(imported_swift_modules(source))
        in_feature = "Features" in path.parts
        in_core_api = "Core" in path.parts and "API" in path.parts
        in_tests = path.parts[-2].endswith("Tests")
        if in_feature:
            for module in sorted(modules & IOS_FEATURE_FORBIDDEN_IMPORTS):
                violations.append(
                    f"{relative.as_posix()} imports forbidden feature-boundary module {module}"
                )
        if "StyleCaptureAPI" in modules and not (in_core_api or in_tests):
            violations.append(
                f"{relative.as_posix()} imports StyleCaptureAPI outside Core/API adapter or tests"
            )
        if "Features" in path.parts:
            feature_index = path.parts.index("Features")
            if len(path.parts) > feature_index + 1:
                feature = path.parts[feature_index + 1]
                for other in (
                    "Onboarding",
                    "Wardrobe",
                    "Packing",
                    "Paywall",
                    "PixelJournal",
                    "Settings",
                ):
                    if other != feature and f"Features/{other}" in source:
                        violations.append(
                            f"{relative.as_posix()} references another feature internals: {other}"
                        )
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
    repository_root = target
    while repository_root.parent != repository_root and not (repository_root / ".git").exists():
        repository_root = repository_root.parent
    violations.extend(check_ios_boundaries(repository_root))
    if violations:
        print("\n".join(violations))
        return 1
    print("architecture boundaries: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
