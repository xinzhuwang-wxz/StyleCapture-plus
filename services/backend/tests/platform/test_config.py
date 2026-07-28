from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from stylecapture_backend.platform.config import (
    PLACEHOLDER_APPLE_GRANT_ENCRYPTION_KEY,
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
    assert settings.demo_seed_new_session_quota == 512
    assert settings.maintenance_queue == "maintenance"
    assert settings.account_revocation_sweep_interval_seconds == 300


def test_account_maintenance_queue_and_sweep_interval_are_configurable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STYLECAPTURE_MAINTENANCE_QUEUE", "account-maintenance")
    monkeypatch.setenv("STYLECAPTURE_ACCOUNT_REVOCATION_SWEEP_INTERVAL_SECONDS", "45")

    settings = BackendSettings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
        redis_url=SecretStr("redis://redis:6379/0"),
        upload_root=tmp_path,
        upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
        session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
    )

    assert settings.maintenance_queue == "account-maintenance"
    assert settings.account_revocation_sweep_interval_seconds == 45


def test_account_maintenance_sweep_interval_must_be_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        BackendSettings(
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
            session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
            account_revocation_sweep_interval_seconds=0,
        )


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
        "apple_provider_grant_encryption_key": SecretStr(
            "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
        ),
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
            apple_team_id="TEAMID1234",
            apple_key_id="KEYID12345",
            apple_private_key_pem=SecretStr("production-apple-private-key"),
            apple_provider_grant_encryption_key=values["apple_provider_grant_encryption_key"],
        )


def test_production_settings_require_complete_apple_server_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError, match="Apple server credentials"):
        BackendSettings(
            environment="production",
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("production-upload-signing-secret-with-entropy"),
            session_signing_secret=SecretStr("production-session-signing-secret-with-entropy"),
            session_cookie_secure=True,
            litellm_api_key=SecretStr("production-gateway-signing-secret-with-entropy"),
            apple_provider_grant_encryption_key=SecretStr(
                "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
            ),
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
        "apple_team_id": "TEAMID1234",
        "apple_key_id": "KEYID12345",
        "apple_private_key_pem": SecretStr("production-apple-private-key"),
        "apple_provider_grant_encryption_key": SecretStr(
            "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
        ),
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


def test_production_settings_reject_local_apple_provider_grant_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError, match="Apple provider grant encryption key"):
        BackendSettings(
            environment="production",
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("production-upload-signing-secret-with-entropy"),
            session_signing_secret=SecretStr("production-session-signing-secret-with-entropy"),
            session_cookie_secure=True,
            litellm_api_key=SecretStr("production-gateway-signing-secret-with-entropy"),
            apple_team_id="TEAMID1234",
            apple_key_id="KEYID12345",
            apple_private_key_pem=SecretStr("production-apple-private-key"),
            apple_provider_grant_encryption_key=SecretStr(PLACEHOLDER_APPLE_GRANT_ENCRYPTION_KEY),
        )


@pytest.mark.parametrize(
    "key",
    [
        f"{PLACEHOLDER_APPLE_GRANT_ENCRYPTION_KEY}\n",
        f"{PLACEHOLDER_APPLE_GRANT_ENCRYPTION_KEY}=",
        "é",
    ],
)
def test_apple_provider_grant_key_rejects_textual_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError, match=r"canonical URL-safe base64|Fernet key"):
        BackendSettings(
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("a-real-signing-secret-with-enough-entropy"),
            session_signing_secret=SecretStr("a-distinct-session-secret-with-enough-entropy"),
            apple_provider_grant_encryption_key=SecretStr(key),
        )


def test_production_apple_provider_grant_key_rejects_public_placeholder_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError, match="local placeholder"):
        BackendSettings(
            environment="production",
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("production-upload-signing-secret-with-entropy"),
            session_signing_secret=SecretStr("production-session-signing-secret-with-entropy"),
            session_cookie_secure=True,
            litellm_api_key=SecretStr("production-gateway-signing-secret-with-entropy"),
            apple_team_id="TEAMID1234",
            apple_key_id="KEYID12345",
            apple_private_key_pem=SecretStr("production-apple-private-key"),
            apple_provider_grant_encryption_key=SecretStr(PLACEHOLDER_APPLE_GRANT_ENCRYPTION_KEY),
        )
