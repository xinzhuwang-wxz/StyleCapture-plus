import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    CoarsePolygonSegmentationProvider,
    Sam2PromptableSegmentationProvider,
)
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.worker_dependencies import build_promptable_segmenter


def _settings(tmp_path: Path, **overrides: Any) -> BackendSettings:
    values: dict[str, Any] = {
        "database_url": SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        "redis_url": SecretStr("redis://redis:6379/0"),
        "upload_root": tmp_path,
        "upload_signing_secret": SecretStr("a-real-signing-secret-with-enough-entropy"),
        "session_signing_secret": SecretStr("a-distinct-session-secret-with-enough-entropy"),
    }
    values.update(overrides)
    return BackendSettings(**values)


def test_worker_segmentation_wiring_keeps_coarse_path_transformers_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Catches: importing the heavy local model stack even when the worker is configured coarse.
    monkeypatch.delitem(sys.modules, "transformers", raising=False)

    segmenter = build_promptable_segmenter(_settings(tmp_path, segmentation_mode="coarse"))

    assert isinstance(segmenter, CoarsePolygonSegmentationProvider)
    assert "transformers" not in sys.modules


def test_worker_segmentation_wiring_selects_sam2_from_settings(tmp_path: Path) -> None:
    # Catches: ignoring the configured segmentation mode/model/device for real refinement.
    segmenter = build_promptable_segmenter(
        _settings(
            tmp_path,
            segmentation_mode="sam2",
            segmentation_model="facebook/sam2.1-hiera-tiny",
            segmentation_model_alias="segmentation_refinement",
            segmentation_device="cpu",
            segmentation_score_threshold=0.82,
        )
    )

    assert isinstance(segmenter, Sam2PromptableSegmentationProvider)
