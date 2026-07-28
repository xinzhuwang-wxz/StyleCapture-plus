from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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


def _nullable_schema() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "components": {
            "schemas": {
                "AppleAuthBody": {
                    "type": "object",
                    "properties": {
                        "device_name": {
                            "anyOf": [
                                {"type": "string", "maxLength": 120},
                                {"type": "null"},
                            ],
                            "title": "Device Name",
                        }
                    },
                }
            }
        },
        "paths": {
            "/v1/account/delete": {
                "post": {
                    "parameters": [
                        {
                            "name": "authorization",
                            "in": "header",
                            "required": False,
                            "schema": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"},
                                ],
                                "title": "Authorization",
                            },
                        }
                    ]
                }
            }
        },
    }


def test_schema_includes_revocable_account_contract() -> None:
    paths = export_openapi.openapi_schema()["paths"]

    assert "/v1/auth/apple" in paths
    assert "/v1/auth/refresh" in paths
    assert "/v1/account/delete" in paths
    assert "/v1/account/deletion-status" not in paths

    delete_operation = paths["/v1/account/delete"]["post"]
    idempotency_header = next(
        parameter
        for parameter in delete_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["in"] == "header"
    assert idempotency_header["required"] is True
    assert idempotency_header["schema"]["minLength"] == 8
    assert idempotency_header["schema"]["maxLength"] == 128
    assert delete_operation["responses"]["202"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DeletionResponse"
    }


def test_swift_projection_preserves_optional_fields_without_null_union() -> None:
    canonical = _nullable_schema()

    projected = export_openapi.swift_openapi_schema(canonical)

    assert canonical["components"]["schemas"]["AppleAuthBody"]["properties"]["device_name"][
        "anyOf"
    ][1] == {"type": "null"}
    device_name = projected["components"]["schemas"]["AppleAuthBody"]["properties"]["device_name"]
    assert device_name == {
        "type": "string",
        "maxLength": 120,
        "title": "Device Name",
    }
    authorization = projected["paths"]["/v1/account/delete"]["post"]["parameters"][0]["schema"]
    assert authorization == {"type": "string", "title": "Authorization"}


def test_swift_projection_keeps_real_union_schemas() -> None:
    canonical = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "null"},
        ],
        "title": "Real Union",
    }

    assert export_openapi.swift_openapi_schema(canonical) == canonical


def test_export_renders_canonical_and_swift_projection_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical_output = tmp_path / "h5" / "openapi.json"
    swift_output = tmp_path / "ios" / "openapi.json"
    schema = _nullable_schema()
    monkeypatch.setattr(export_openapi, "openapi_schema", lambda: schema)

    export_openapi.export([canonical_output], [swift_output])

    assert canonical_output.read_bytes() == export_openapi.schema_bytes(schema)
    assert swift_output.read_bytes() == export_openapi.schema_bytes(
        export_openapi.swift_openapi_schema(schema)
    )
    assert export_openapi.export([canonical_output], [swift_output], check=True) == [
        canonical_output,
        swift_output,
    ]


def test_check_mode_fails_when_output_is_missing_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "missing" / "openapi.json"
    monkeypatch.setattr(export_openapi, "schema_bytes", lambda *_: b'{"openapi":"3.1.0"}\n')

    with pytest.raises(SystemExit):
        export_openapi.export([output], check=True)

    assert not output.exists()
    assert not output.parent.exists()


def test_check_mode_fails_when_output_differs_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "openapi.json"
    output.write_bytes(b'{"old":true}\n')
    monkeypatch.setattr(export_openapi, "schema_bytes", lambda *_: b'{"openapi":"3.1.0"}\n')

    with pytest.raises(SystemExit):
        export_openapi.export([output], check=True)

    assert output.read_bytes() == b'{"old":true}\n'
