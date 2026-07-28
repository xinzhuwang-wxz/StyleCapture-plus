from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPOSITORY_ROOT / "scripts" / "export_openapi.py"


def _load_export_openapi() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stylecapture_export_openapi", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


export_openapi = _load_export_openapi()


def test_schema_includes_revocable_account_contract() -> None:
    paths = export_openapi.openapi_schema()["paths"]

    assert "/v1/auth/apple" in paths
    assert "/v1/auth/refresh" in paths
    assert "/v1/account/delete" in paths
    assert "/v1/account/deletion-status" in paths


def test_check_mode_fails_when_output_is_missing_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "missing" / "openapi.json"
    monkeypatch.setattr(export_openapi, "schema_bytes", lambda: b'{"openapi":"3.1.0"}\n')

    with pytest.raises(SystemExit):
        export_openapi.export([output], check=True)

    assert not output.exists()
    assert not output.parent.exists()


def test_check_mode_fails_when_output_differs_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "openapi.json"
    output.write_bytes(b'{"old":true}\n')
    monkeypatch.setattr(export_openapi, "schema_bytes", lambda: b'{"openapi":"3.1.0"}\n')

    with pytest.raises(SystemExit):
        export_openapi.export([output], check=True)

    assert output.read_bytes() == b'{"old":true}\n'
