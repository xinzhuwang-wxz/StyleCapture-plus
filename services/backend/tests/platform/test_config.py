from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from stylecapture_backend.platform.config import BackendSettings


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
        cors_origins=["http://localhost:5173"],
    )

    serialized = settings.model_dump_json()

    assert "a-real-signing-secret" not in serialized
    assert settings.upload_signing_secret.get_secret_value().startswith("a-real")
    assert settings.vision_model_alias == "vision-understanding"


def test_production_settings_reject_the_documented_placeholder_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        BackendSettings(
            environment="production",
            database_url=SecretStr("postgresql+asyncpg://user:pass@postgres/stylecapture"),
            redis_url=SecretStr("redis://redis:6379/0"),
            upload_root=tmp_path,
            upload_signing_secret=SecretStr("replace-with-at-least-24-random-characters"),
        )
