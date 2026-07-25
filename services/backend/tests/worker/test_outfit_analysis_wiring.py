from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.worker_dependencies import build_outfit_analyzer

VALID_ANALYSIS = """
{
  "color": {"value": "米白与藏青", "confidence": 0.91},
  "silhouette": {"value": "宽松直筒", "confidence": 0.87},
  "material": {"value": "亚麻与棉", "confidence": 0.82},
  "layering": {"value": "衬衫叠搭长裤", "confidence": 0.84},
  "focal_point": {"value": "敞开领口", "confidence": 0.79},
  "scene": {"value": "城市街道", "confidence": 0.76},
  "style": {"value": "极简休闲", "confidence": 0.92}
}
"""


class FailThenSucceedCompletion:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise ConnectionError("primary unavailable")
        return SimpleNamespace(
            model="provider-outfit-v1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=VALID_ANALYSIS))],
        )


def _settings(tmp_path: Path) -> BackendSettings:
    return BackendSettings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        redis_url=SecretStr("redis://redis:6379/0"),
        upload_root=tmp_path,
        upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
        session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
        outfit_analysis_model_alias="outfit_analysis",
        outfit_analysis_fallback_model_alias="outfit_analysis_fallback",
    )


def _image() -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", (40, 60), color=(220, 210, 190)).save(buffer, format="PNG")
    return ImagePayload(
        object_key="originals/feed/frame.png",
        content_type="image/png",
        body=buffer.getvalue(),
        sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_worker_wires_stable_outfit_alias_to_sequential_fallback(tmp_path: Path) -> None:
    # Catches: worker assembly dropping the server-only Lite fallback alias.
    completion = FailThenSucceedCompletion()
    analyzer = build_outfit_analyzer(_settings(tmp_path), completion=completion)

    analysis = await analyzer.analyze(_image(), components=())

    assert [call["model"] for call in completion.calls] == [
        "openai/outfit_analysis",
        "openai/outfit_analysis_fallback",
    ]
    assert analysis.metadata.capability_alias == "outfit_analysis"
