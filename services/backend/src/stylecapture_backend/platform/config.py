from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SIGNING_SECRET = "replace-with-at-least-24-random-characters"
PLACEHOLDER_SESSION_SECRET = "replace-with-a-distinct-session-signing-secret"
PLACEHOLDER_GATEWAY_SECRET = "local-litellm-gateway-key-change-before-production"


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
    session_signing_secret: SecretStr
    apple_client_ids: list[str] = ["com.stylecapture.journey"]
    apple_team_id: str | None = None
    apple_key_id: str | None = None
    apple_private_key_pem: SecretStr = SecretStr("")
    session_cookie_secure: bool = False
    public_upload_prefix: str = "/v1/uploads"
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024
    max_image_pixels: int = 36_000_000
    vision_model_alias: str = "vision_understanding"
    grounding_model_alias: str = "visual_grounding"
    outfit_analysis_model_alias: str = "outfit_analysis"
    outfit_analysis_fallback_model_alias: str = "outfit_analysis_fallback"
    reasoning_model_alias: str = "reasoning"
    outfit_reasoning_timeout_seconds: float = 60
    image_generation_model_alias: str = "image_generation"
    segmentation_mode: Literal["coarse", "sam2"] = "sam2"
    segmentation_model_alias: str = "segmentation_refinement"
    segmentation_model: str = "facebook/sam2.1-hiera-tiny"
    segmentation_device: str = "cpu"
    segmentation_score_threshold: float = 0.7
    litellm_base_url: str = "http://litellm:4000/v1"
    litellm_api_key: SecretStr = SecretStr(PLACEHOLDER_GATEWAY_SECRET)
    embedding_mode: Literal["hosted", "fashion_siglip", "disabled"] = "hosted"
    embedding_model: str = "doubao-embedding-vision-250615"
    embedding_device: str = "cpu"
    capture_queue: str = "capture"
    render_queue: str = "render"
    worker_max_retries: int = 2
    # Seedream commonly completes just beyond 45s. A 75s request window avoids
    # two full provider retries and cuts observed pixel-trial latency from
    # roughly 135s to one generation request.
    render_request_timeout_seconds: float = 75
    render_poll_interval_seconds: float = 1
    render_poll_timeout_seconds: float = 90
    render_download_max_bytes: int = 20 * 1024 * 1024
    fashn_api_base: str = "https://api.fashn.ai/v1"
    fashn_api_key: SecretStr = SecretStr("")
    fixed_model_object_key: str | None = None
    demo_seed_enabled: bool = True
    demo_seed_new_session_quota: int = 512
    ai_cost_window_seconds: int = 600
    ai_cost_actor_requests: int = 8
    ai_cost_client_requests: int = 20
    ai_cost_global_requests: int = 160
    ai_cost_actor_concurrency: int = 1
    ai_cost_client_concurrency: int = 3
    ai_cost_global_concurrency: int = 12

    @field_validator("upload_signing_secret", "session_signing_secret")
    @classmethod
    def validate_signing_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 24:
            raise ValueError("signing secrets must be at least 24 characters")
        return value

    @field_validator(
        "max_upload_bytes",
        "max_image_pixels",
        "render_download_max_bytes",
        "demo_seed_new_session_quota",
        "ai_cost_window_seconds",
        "ai_cost_actor_requests",
        "ai_cost_client_requests",
        "ai_cost_global_requests",
        "ai_cost_actor_concurrency",
        "ai_cost_client_concurrency",
        "ai_cost_global_concurrency",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("resource limits must be positive")
        return value

    @field_validator("capture_queue", "render_queue")
    @classmethod
    def validate_queue(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 80:
            raise ValueError("capture queue must contain between 1 and 80 characters")
        return value

    @field_validator("apple_client_ids")
    @classmethod
    def validate_apple_client_ids(cls, value: list[str]) -> list[str]:
        if not value or any(not client_id.strip() for client_id in value):
            raise ValueError("at least one Apple client ID is required")
        return [client_id.strip() for client_id in value]

    @field_validator(
        "render_request_timeout_seconds",
        "render_poll_interval_seconds",
        "render_poll_timeout_seconds",
        "outfit_reasoning_timeout_seconds",
    )
    @classmethod
    def validate_render_timeouts(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("render timeouts and intervals must be positive")
        return value

    @field_validator("segmentation_score_threshold")
    @classmethod
    def validate_segmentation_score_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("segmentation score threshold must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def reject_production_placeholders(self) -> BackendSettings:
        apple_credentials = (
            bool(self.apple_team_id and self.apple_team_id.strip()),
            bool(self.apple_key_id and self.apple_key_id.strip()),
            bool(self.apple_private_key_pem.get_secret_value().strip()),
        )
        if any(apple_credentials) and not all(apple_credentials):
            raise ValueError("Apple server credentials must be configured together")
        if self.environment == "production":
            if "demo_seed_enabled" not in self.model_fields_set:
                self.demo_seed_enabled = False
            if self.upload_signing_secret.get_secret_value() == PLACEHOLDER_SIGNING_SECRET:
                raise ValueError("production signing secret cannot use the documented placeholder")
            if self.session_signing_secret.get_secret_value() == PLACEHOLDER_SESSION_SECRET:
                raise ValueError("production session secret cannot use the documented placeholder")
            if not self.session_cookie_secure:
                raise ValueError("production session cookies must be secure")
            if self.litellm_api_key.get_secret_value() == PLACEHOLDER_GATEWAY_SECRET:
                raise ValueError("production gateway secret cannot use the local placeholder")
            if not all(apple_credentials):
                raise ValueError("Apple server credentials are required in production")
        return self
