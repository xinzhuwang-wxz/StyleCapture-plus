from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stylecapture_backend.features.wardrobe.domain import WHOLE_CAPTURE_SELECTION_KEY
from stylecapture_backend.platform.database import Base


class ItemRecord(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_user_created", "user_id", "created_at"),
        Index("ix_items_user_status", "user_id", "status"),
        UniqueConstraint(
            "capture_id",
            "selection_key",
            name="uq_items_capture_id_selection_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    capture_id: Mapped[UUID] = mapped_column(
        ForeignKey("captures.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selection_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=WHOLE_CAPTURE_SELECTION_KEY,
        server_default=WHOLE_CAPTURE_SELECTION_KEY,
    )
    source_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    source_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ownership: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    subcategory: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(1000))
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    model_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
