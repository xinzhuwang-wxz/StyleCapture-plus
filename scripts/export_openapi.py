from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.look.interfaces.http import LookHttpServices
from stylecapture_backend.features.outfit.application import OutfitApplication
from stylecapture_backend.features.outfit.interfaces.http import OutfitHttpServices
from stylecapture_backend.features.outfit.ports import OutfitPlanTickets
from stylecapture_backend.features.render.interfaces.http import RenderHttpServices
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


def export() -> Path:
    repository_root = Path(__file__).resolve().parents[1]
    output = repository_root / "apps" / "h5" / "openapi.json"
    services = BackendServices(
        capture=cast(CaptureApplication, None),
        jobs=cast(JobRepository, None),
        objects=cast(ObjectStore, None),
        retries=cast(JobRetryApplication, None),
        wardrobe=cast(WardrobeApplication, None),
        looks=cast(LookHttpServices, object()),
        renders=cast(RenderHttpServices, object()),
        outfits=OutfitHttpServices(
            outfits=cast(OutfitApplication, None),
            tickets=cast(OutfitPlanTickets, None),
        ),
        demo_wardrobe=None,
    )
    schema = create_app(services).openapi()
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    print(export())
