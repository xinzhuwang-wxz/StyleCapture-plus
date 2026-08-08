from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from stylecapture_backend.platform.database import Base


class PixelTrialRecord(Base):
    __tablename__ = "pixel_trials"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="pixel_trial_status",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status <> 'succeeded' AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="pixel_trial_output_status",
        ),
        CheckConstraint(
            "status = 'failed' OR failure_code IS NULL",
            name="pixel_trial_failure_code_status",
        ),
        CheckConstraint(
            "(sprite_object_key IS NULL AND sprite_content_hash IS NULL "
            "AND sprite_content_type IS NULL) OR "
            "(sprite_object_key IS NOT NULL AND sprite_content_hash IS NOT NULL "
            "AND sprite_content_type IS NOT NULL)",
            name="pixel_trial_sprite_output_complete",
        ),
        Index("ix_pixel_trials_user_created", "user_id", "created_at"),
        Index("ix_pixel_trials_user_request_key", "user_id", "request_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    subject_object_key: Mapped[str | None] = mapped_column(String(512))
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content_type: Mapped[str | None] = mapped_column(String(80))
    sprite_object_key: Mapped[str | None] = mapped_column(String(512))
    sprite_content_hash: Mapped[str | None] = mapped_column(String(64))
    sprite_content_type: Mapped[str | None] = mapped_column(String(80))
    subject_attached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    provider_trace: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
