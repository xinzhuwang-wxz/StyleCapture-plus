from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, cast

from stylecapture_backend.features.account.application import AccountApplication
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import (
    JobRepository,
    ObjectStore,
    UploadAcceptor,
)
from stylecapture_backend.features.item_presentation.interfaces.http import (
    ItemPresentationHttpServices,
)
from stylecapture_backend.features.look.interfaces.http import LookHttpServices
from stylecapture_backend.features.outfit.application import OutfitApplication
from stylecapture_backend.features.outfit.interfaces.http import OutfitHttpServices
from stylecapture_backend.features.outfit.ports import OutfitPlanTickets
from stylecapture_backend.features.pixel_trial.interfaces.http import PixelTrialHttpServices
from stylecapture_backend.features.render.interfaces.http import RenderHttpServices
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


def openapi_schema() -> dict:
    services = BackendServices(
        capture=cast(CaptureApplication, None),
        jobs=cast(JobRepository, None),
        objects=cast(ObjectStore, None),
        retries=cast(JobRetryApplication, None),
        wardrobe=cast(WardrobeApplication, None),
        looks=cast(LookHttpServices, object()),
        renders=cast(RenderHttpServices, object()),
        pixel_trials=cast(PixelTrialHttpServices, object()),
        item_presentations=cast(ItemPresentationHttpServices, object()),
        outfits=OutfitHttpServices(
            outfits=cast(OutfitApplication, None),
            tickets=cast(OutfitPlanTickets, None),
        ),
        demo_wardrobe=None,
        accounts=cast(AccountApplication, object()),
        uploads=cast(UploadAcceptor, object()),
    )
    return create_app(services).openapi()


def swift_openapi_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Project OpenAPI 3.1 nullable schemas into generator-supported optionals.

    Swift OpenAPI Generator 1.13.0 skips the ``null`` member in FastAPI's
    ``anyOf: [T, null]`` representation. Collapsing only that exact two-member
    shape preserves optionality through the containing object's ``required``
    list or the parameter's ``required`` flag, while leaving real unions alone.
    """

    return cast(dict[str, Any], _swift_openapi_value(schema))


def _swift_openapi_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_swift_openapi_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    any_of = value.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        null_members = [
            member
            for member in any_of
            if isinstance(member, dict) and member.get("type") == "null"
        ]
        non_null_members = [
            member
            for member in any_of
            if not (isinstance(member, dict) and member.get("type") == "null")
        ]
        if len(null_members) == 1 and len(non_null_members) == 1:
            projected = _swift_openapi_value(non_null_members[0])
            if isinstance(projected, dict):
                siblings = {
                    key: _swift_openapi_value(item)
                    for key, item in value.items()
                    if key != "anyOf"
                }
                return {**projected, **siblings}

    return {key: _swift_openapi_value(item) for key, item in value.items()}


def schema_bytes(schema: dict[str, Any] | None = None) -> bytes:
    return (
        json.dumps(
            schema if schema is not None else openapi_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def export(
    outputs: list[Path] | None = None,
    swift_outputs: list[Path] | None = None,
    check: bool = False,
) -> list[Path]:
    repository_root = Path(__file__).resolve().parents[1]
    selected_outputs = (
        outputs
        if outputs is not None
        else [repository_root / "apps" / "h5" / "openapi.json"]
    )
    canonical = openapi_schema()
    render_groups = (
        (selected_outputs, schema_bytes(canonical)),
        (swift_outputs or [], schema_bytes(swift_openapi_schema(canonical))),
    )
    written: list[Path] = []
    for group, rendered in render_groups:
        for output in group:
            path = output if output.is_absolute() else repository_root / output
            if check:
                try:
                    display_path = path.relative_to(repository_root)
                except ValueError:
                    display_path = path
                if not path.exists():
                    print(f"OpenAPI schema is missing: {display_path}", file=sys.stderr)
                    raise SystemExit(1)
                if path.read_bytes() != rendered:
                    print(f"OpenAPI schema is stale: {display_path}", file=sys.stderr)
                    raise SystemExit(1)
                written.append(path)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(rendered)
            written.append(path)
    return written


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--output", action="append", type=Path)
    parser.add_argument("--swift-output", action="append", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path in export(args.output, args.swift_output, args.check):
        print(path)
