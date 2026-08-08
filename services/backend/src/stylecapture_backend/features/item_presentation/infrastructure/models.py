from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from stylecapture_backend.platform.database import Base


class ItemPresentationAssetRecord(Base):
    __tablename__ = "item_presentation_assets"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('pixel_item','flat_lay_item')",
            name="item_presentation_kind",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="item_presentation_status",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status <> 'succeeded' AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="item_presentation_output_status",
        ),
        CheckConstraint(
            "status = 'failed' OR failure_code IS NULL",
            name="item_presentation_failure_code_status",
        ),
        Index("ix_item_presentations_user_item", "user_id", "item_id"),
        Index("ix_item_presentations_user_request_key", "user_id", "request_key", unique=True),
        Index(
            "ix_item_presentations_current",
            "user_id",
            "item_id",
            "kind",
            "input_version",
            "input_hash",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content_type: Mapped[str | None] = mapped_column(String(80))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    provider_trace: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
