from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
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
    )
    return create_app(services).openapi()


def schema_bytes() -> bytes:
    return (
        json.dumps(openapi_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def export(outputs: list[Path] | None = None, check: bool = False) -> list[Path]:
    repository_root = Path(__file__).resolve().parents[1]
    selected_outputs = outputs or [repository_root / "apps" / "h5" / "openapi.json"]
    rendered = schema_bytes()
    written: list[Path] = []
    for output in selected_outputs:
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
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path in export(args.output, args.check):
        print(path)
