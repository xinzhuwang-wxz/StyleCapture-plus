from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stylecapture_backend.platform.database import Base


class RenderArtifactRecord(Base):
    __tablename__ = "render_artifacts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('collage','try_on','pixel_cover')",
            name="render_artifact_kind",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','degraded')",
            name="render_artifact_status",
        ),
        CheckConstraint(
            "privacy IN ('private','shareable_pixel')",
            name="render_artifact_privacy",
        ),
        CheckConstraint(
            "(status IN ('succeeded','degraded') AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status NOT IN ('succeeded','degraded') AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="render_artifact_output_status",
        ),
        CheckConstraint(
            "status <> 'degraded' OR fallback_artifact_id IS NOT NULL",
            name="render_artifact_degraded_fallback",
        ),
        CheckConstraint(
            "privacy <> 'shareable_pixel' OR kind = 'pixel_cover'",
            name="render_artifact_shareable_pixel_kind",
        ),
        Index("ix_render_artifacts_look_created", "look_id", "created_at"),
        Index("ix_render_artifacts_user_request_key", "user_id", "request_key", unique=True),
        Index(
            "ix_render_artifacts_cache_hit",
            "look_id",
            "kind",
            "input_version",
            "input_hash",
            unique=True,
            postgresql_where=text(
                "status IN ('succeeded','degraded') AND object_key IS NOT NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    look_id: Mapped[UUID] = mapped_column(
        ForeignKey("looks.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    privacy: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content_type: Mapped[str | None] = mapped_column(String(80))
    share_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("render_artifacts.id", ondelete="SET NULL")
    )
    fallback_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("render_artifacts.id", ondelete="RESTRICT")
    )
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    provider_trace: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
