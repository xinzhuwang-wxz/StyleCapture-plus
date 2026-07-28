from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
IOS_ROOT = REPOSITORY_ROOT / "apps" / "ios" / "StyleCaptureJourney"
PACKAGE_GRAPH_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_ios_package_graph.py"
CAPABILITY_PATCH_SCRIPT = REPOSITORY_ROOT / "scripts" / "patch_ios_system_capabilities.py"
PRIVACY_MANIFEST_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_ios_privacy_manifest.py"
PACKAGE_RESOLVED = IOS_ROOT / "Config" / "Package.resolved"
PROJECT_SPEC = IOS_ROOT / "project.yml"
ENTITLEMENTS = IOS_ROOT / "StyleCaptureJourney" / "Resources" / "StyleCaptureJourney.entitlements"
PRIVACY_MANIFEST = IOS_ROOT / "StyleCaptureJourney" / "Resources" / "PrivacyInfo.xcprivacy"
NOTICES = IOS_ROOT / "StyleCaptureJourney" / "Resources" / "ThirdPartyNotices.txt"
APP_FEATURE = IOS_ROOT / "StyleCaptureJourney" / "App" / "AppFeature.swift"
APPLE_SIGN_IN_BUTTON = (
    IOS_ROOT
    / "StyleCaptureJourney"
    / "Features"
    / "Onboarding"
    / "AppleSignInTriggerButton.swift"
)
AUTH_SESSION = IOS_ROOT / "StyleCaptureJourney" / "Core" / "Auth" / "AuthSession.swift"
NAVIGATION_CLIENT = (
    IOS_ROOT
    / "StyleCaptureJourney"
    / "Core"
    / "Navigation"
    / "NavigationSnapshotClient.swift"
)
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
privacy_manifest = _load_module("stylecapture_ios_privacy_manifest", PRIVACY_MANIFEST_SCRIPT)


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


def test_application_target_explicitly_links_http_types() -> None:
    project_spec = PROJECT_SPEC.read_text(encoding="utf-8")
    application_target = project_spec.split("  StyleCaptureJourney:\n", maxsplit=1)[1].split(
        "  StyleCaptureJourneyTests:\n", maxsplit=1
    )[0]

    assert "- package: swift-http-types\n        product: HTTPTypes" in application_target


def test_native_shell_reuses_tca_and_apple_surfaces_without_duplicate_infrastructure() -> None:
    app_feature = APP_FEATURE.read_text(encoding="utf-8")
    apple_button = APPLE_SIGN_IN_BUTTON.read_text(encoding="utf-8")

    assert ".fileStorage(.styleCaptureNavigationSnapshot)" in app_feature
    assert "Result<Void" not in app_feature
    assert not NAVIGATION_CLIENT.exists()
    assert not AUTH_SESSION.exists()
    assert "ASAuthorizationAppleIDButton(type: .signIn, style: .black)" in apple_button


def test_dependency_privacy_evidence_records_packaged_sdk_manifests() -> None:
    evidence = PRIVACY_EVIDENCE.read_text(encoding="utf-8")

    assert "GRDB/PrivacyInfo.xcprivacy" in evidence
    assert "NSPrivacyAccessedAPICategoryUserDefaults` / `C56D.1" in evidence
    assert "NSPrivacyAccessedAPICategoryFileTimestamp` / `C617.1" in evidence
    assert "swift-sharing/Sources/Sharing/PrivacyInfo.xcprivacy" in evidence


def test_application_privacy_manifest_declares_sign_in_user_id_collection() -> None:
    with PRIVACY_MANIFEST.open("rb") as manifest_file:
        manifest = plistlib.load(manifest_file)

    user_id_entries = [
        entry
        for entry in manifest["NSPrivacyCollectedDataTypes"]
        if entry["NSPrivacyCollectedDataType"] == "NSPrivacyCollectedDataTypeUserID"
    ]

    assert user_id_entries == [
        {
            "NSPrivacyCollectedDataType": "NSPrivacyCollectedDataTypeUserID",
            "NSPrivacyCollectedDataTypeLinked": True,
            "NSPrivacyCollectedDataTypePurposes": [
                "NSPrivacyCollectedDataTypePurposeAppFunctionality"
            ],
            "NSPrivacyCollectedDataTypeTracking": False,
        }
    ]


def test_application_privacy_manifest_does_not_duplicate_sdk_required_reasons() -> None:
    with PRIVACY_MANIFEST.open("rb") as manifest_file:
        manifest = plistlib.load(manifest_file)

    assert manifest["NSPrivacyAccessedAPITypes"] == []
    assert privacy_manifest.source_uses_user_defaults() is False


def test_privacy_manifest_validator_rejects_missing_sign_in_user_id_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "PrivacyInfo.xcprivacy"
    with PRIVACY_MANIFEST.open("rb") as manifest_file:
        manifest = plistlib.load(manifest_file)
    manifest["NSPrivacyCollectedDataTypes"] = []
    with manifest_path.open("wb") as manifest_file:
        plistlib.dump(manifest, manifest_file)

    monkeypatch.setattr(privacy_manifest, "PRIVACY_MANIFEST", manifest_path)

    assert privacy_manifest.main([]) == 1
    assert "missing linked non-tracking User ID" in capsys.readouterr().err


def test_distributable_notices_cover_every_resolved_dependency() -> None:
    notices = NOTICES.read_text(encoding="utf-8")

    for identity, state in _resolved_pins().items():
        assert identity in notices
        assert state["version"] in notices
        assert state["revision"] in notices

    assert "MIT License" in notices
    assert "Apache License\nVersion 2.0, January 2004" in notices


def test_reducers_and_views_do_not_expose_secret_tokens_in_observable_state() -> None:
    source_roots = [
        IOS_ROOT / "StyleCaptureJourney" / "App",
        IOS_ROOT / "StyleCaptureJourney" / "Features",
    ]
    violations: list[str] = []

    for source_root in source_roots:
        for source_file in sorted(source_root.rglob("*.swift")):
            source = source_file.read_text(encoding="utf-8")
            relative_path = source_file.relative_to(REPOSITORY_ROOT)

            for line_number, line in enumerate(source.splitlines(), start=1):
                if "accessToken" in line or "refreshToken" in line:
                    violations.append(
                        f"{relative_path}:{line_number} references raw token field"
                    )

                if "case signedIn(AuthTokens)" in line:
                    violations.append(
                        f"{relative_path}:{line_number} stores AuthTokens in signed-in UI state"
                    )

                if "case confirmingAccountDeletion(AuthTokens)" in line:
                    violations.append(
                        f"{relative_path}:{line_number} stores AuthTokens in account-deletion UI state"
                    )

            if "@ObservableState" in source and "AuthTokens" in source:
                violations.append(
                    f"{relative_path} keeps AuthTokens reachable from observable reducer state"
                )

    assert violations == []
