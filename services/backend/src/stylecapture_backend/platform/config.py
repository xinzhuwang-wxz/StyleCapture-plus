from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SIGNING_SECRET = "replace-with-at-least-24-random-characters"


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="STYLECAPTURE_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    redis_url: SecretStr
    upload_root: Path
    upload_signing_secret: SecretStr
    public_upload_prefix: str = "/v1/uploads"
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024
    max_image_pixels: int = 36_000_000
    vision_model_alias: str = "vision-understanding"

    @field_validator("upload_signing_secret")
    @classmethod
    def validate_signing_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 24:
            raise ValueError("upload signing secret must be at least 24 characters")
        return value

    @field_validator("max_upload_bytes", "max_image_pixels")
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("resource limits must be positive")
        return value

    @model_validator(mode="after")
    def reject_production_placeholders(self) -> BackendSettings:
        if (
            self.environment == "production"
            and self.upload_signing_secret.get_secret_value() == PLACEHOLDER_SIGNING_SECRET
        ):
            raise ValueError("production signing secret cannot use the documented placeholder")
        return self
