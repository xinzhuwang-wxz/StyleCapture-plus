from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from stylecapture_backend.platform.config import (
    PLACEHOLDER_GATEWAY_SECRET,
    PLACEHOLDER_SESSION_SECRET,
    PLACEHOLDER_SIGNING_SECRET,
    BackendSettings,
)


def test_settings_keep_runtime_secrets_out_of_plain_serialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = BackendSettings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        redis_url=SecretStr("redis://redis:6379/0"),
        upload_root=tmp_path,
        upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
        session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
        cors_origins=["http://localhost:5173"],
    )

    serialized = settings.model_dump_json()

    assert "a-real-signing-secret" not in serialized
    assert "a-distinct-session-secret" not in serialized
    assert "local-litellm-gateway-key" not in serialized
    assert settings.upload_signing_secret.get_secret_value().startswith("a-real")
    assert settings.vision_model_alias == "vision_understanding"
    assert settings.grounding_model_alias == "visual_grounding"
    assert settings.embedding_mode == "hosted"
    assert settings.embedding_model == "doubao-embedding-vision-250615"
    assert settings.segmentation_mode == "sam2"
    assert settings.segmentation_model_alias == "segmentation_refinement"
    assert settings.segmentation_model == "facebook/sam2.1-hiera-tiny"
    assert settings.segmentation_device == "cpu"
    assert settings.segmentation_score_threshold == 0.7
    assert settings.outfit_reasoning_timeout_seconds == 60
    assert settings.outfit_analysis_model_alias == "outfit_analysis"
    assert settings.outfit_analysis_fallback_model_alias == "outfit_analysis_fallback"
    assert settings.try_on_skill_path.name == "virtual_try_on.py"
    assert settings.try_on_skill_timeout_seconds == 1800
    assert settings.try_on_understanding_model == "doubao-seed-2-0-lite-260428"
    assert settings.try_on_image_model == "doubao-seedream-5-0-260128"
    assert settings.demo_seed_new_session_quota == 512


@pytest.mark.parametrize(
    ("field", "placeholder"),
    [
        ("upload_signing_secret", PLACEHOLDER_SIGNING_SECRET),
        ("session_signing_secret", PLACEHOLDER_SESSION_SECRET),
        ("litellm_api_key", PLACEHOLDER_GATEWAY_SECRET),
    ],
)
def test_production_settings_reject_every_local_compose_placeholder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    placeholder: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    values = {
        "upload_signing_secret": SecretStr("production-upload-signing-secret-with-entropy"),
        "session_signing_secret": SecretStr("production-session-signing-secret-with-entropy"),
        "litellm_api_key": SecretStr("production-gateway-signing-secret-with-entropy"),
    }
    values[field] = SecretStr(placeholder)
    with pytest.raises(ValidationError):
        BackendSettings(
            environment="production",
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=values["upload_signing_secret"],
            session_signing_secret=values["session_signing_secret"],
            session_cookie_secure=True,
            litellm_api_key=values["litellm_api_key"],
        )


def test_segmentation_settings_can_select_sam2_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Catches: worker/runtime config being fixed to coarse despite env selection.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STYLECAPTURE_SEGMENTATION_MODE", "sam2")
    monkeypatch.setenv("STYLECAPTURE_SEGMENTATION_DEVICE", "mps")
    monkeypatch.setenv("STYLECAPTURE_SEGMENTATION_SCORE_THRESHOLD", "0.83")

    settings = BackendSettings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        redis_url=SecretStr("redis://redis:6379/0"),
        upload_root=tmp_path,
        upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
        session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
    )

    assert settings.segmentation_mode == "sam2"
    assert settings.segmentation_device == "mps"
    assert settings.segmentation_score_threshold == 0.83


def test_demo_seed_defaults_on_locally_but_off_in_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    common: dict[str, Any] = {
        "database_url": SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        "redis_url": SecretStr("redis://redis:6379/0"),
        "upload_root": tmp_path,
        "upload_signing_secret": SecretStr("production-upload-signing-secret-with-entropy"),
        "session_signing_secret": SecretStr("production-session-signing-secret-with-entropy"),
        "litellm_api_key": SecretStr("production-gateway-signing-secret-with-entropy"),
    }

    development = BackendSettings(**common)
    production = BackendSettings(
        **common,
        environment="production",
        session_cookie_secure=True,
    )
    explicitly_seeded_production = BackendSettings(
        **common,
        environment="production",
        session_cookie_secure=True,
        demo_seed_enabled=True,
    )

    assert development.demo_seed_enabled is True
    assert production.demo_seed_enabled is False
    assert explicitly_seeded_production.demo_seed_enabled is True
