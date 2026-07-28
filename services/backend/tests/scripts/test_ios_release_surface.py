from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
IOS_ROOT = REPOSITORY_ROOT / "apps" / "ios" / "StyleCaptureJourney"
PACKAGE_GRAPH_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_ios_package_graph.py"
CAPABILITY_PATCH_SCRIPT = REPOSITORY_ROOT / "scripts" / "patch_ios_system_capabilities.py"
PACKAGE_RESOLVED = IOS_ROOT / "Config" / "Package.resolved"
PROJECT_SPEC = IOS_ROOT / "project.yml"
ENTITLEMENTS = IOS_ROOT / "StyleCaptureJourney" / "Resources" / "StyleCaptureJourney.entitlements"
NOTICES = IOS_ROOT / "StyleCaptureJourney" / "Resources" / "ThirdPartyNotices.txt"
PRIVACY_EVIDENCE = (
    REPOSITORY_ROOT
    / "docs"
    / "evidence"
    / "journey"
    / "task-2"
    / "dependency-license-privacy-audit.md"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package_graph = _load_module("stylecapture_ios_package_graph", PACKAGE_GRAPH_SCRIPT)
capability_patch = _load_module("stylecapture_ios_capability_patch", CAPABILITY_PATCH_SCRIPT)


def _resolved_pins() -> dict[str, dict[str, str]]:
    resolved = json.loads(PACKAGE_RESOLVED.read_text(encoding="utf-8"))
    return {pin["identity"]: pin["state"] for pin in resolved["pins"]}


def test_package_graph_enforces_every_resolved_pin() -> None:
    assert {
        identity: (state["version"], state["revision"])
        for identity, state in _resolved_pins().items()
    } == package_graph.EXPECTED_PINS


def test_sign_in_with_apple_capability_is_declared_in_source_control() -> None:
    with ENTITLEMENTS.open("rb") as entitlements_file:
        entitlements = plistlib.load(entitlements_file)

    assert entitlements["com.apple.developer.applesignin"] == ["Default"]

    project_spec = PROJECT_SPEC.read_text(encoding="utf-8")
    relative_entitlements = "StyleCaptureJourney/Resources/StyleCaptureJourney.entitlements"
    assert f"CODE_SIGN_ENTITLEMENTS: {relative_entitlements}" in project_spec
    assert "SystemCapabilities:" in project_spec
    assert "com.apple.SignInWithApple:" in project_spec
    assert "enabled: 1" in project_spec
    assert "patch_ios_system_capabilities.py" in project_spec


def test_xcodegen_system_capability_is_normalized_to_pbx_dictionary(tmp_path: Path) -> None:
    pbxproj = tmp_path / "project.pbxproj"
    pbxproj.write_text(
        '\t\tSystemCapabilities = "[\\"com.apple.SignInWithApple\\": [\\"enabled\\": 1]]";\n',
        encoding="utf-8",
    )

    capability_patch.normalize_system_capabilities(pbxproj)

    normalized = pbxproj.read_text(encoding="utf-8")
    assert "SystemCapabilities = {" in normalized
    assert "com.apple.SignInWithApple = {" in normalized
    assert "enabled = 1;" in normalized
    assert 'SystemCapabilities = "' not in normalized


def test_dependency_privacy_evidence_records_packaged_sdk_manifests() -> None:
    evidence = PRIVACY_EVIDENCE.read_text(encoding="utf-8")

    assert "GRDB/PrivacyInfo.xcprivacy" in evidence
    assert "NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1" in evidence
    assert "NSPrivacyAccessedAPICategoryFileTimestamp` / `C617.1" in evidence
    assert "swift-sharing/Sources/Sharing/PrivacyInfo.xcprivacy" in evidence


def test_distributable_notices_cover_every_resolved_dependency() -> None:
    notices = NOTICES.read_text(encoding="utf-8")

    for identity, state in _resolved_pins().items():
        assert identity in notices
        assert state["version"] in notices
        assert state["revision"] in notices

    assert "MIT License" in notices
    assert "Apache License\nVersion 2.0, January 2004" in notices
