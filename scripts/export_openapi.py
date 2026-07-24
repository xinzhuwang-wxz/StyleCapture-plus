from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from stylecapture_backend.features.capture.application import CaptureApplication
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.main import BackendServices, create_app


def export() -> Path:
    repository_root = Path(__file__).resolve().parents[1]
    output = repository_root / "apps" / "h5" / "openapi.json"
    services = BackendServices(
        capture=cast(CaptureApplication, None),
        jobs=cast(JobRepository, None),
        objects=cast(ObjectStore, None),
    )
    schema = create_app(services).openapi()
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    print(export())
