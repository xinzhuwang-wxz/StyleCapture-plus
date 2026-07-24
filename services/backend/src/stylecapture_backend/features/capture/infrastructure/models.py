from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stylecapture_backend.platform.database import Base


class CaptureRecord(Base):
    __tablename__ = "captures"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_captures_user_id_idempotency_key"),
        Index("ix_captures_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_ref: Mapped[str | None] = mapped_column(String(512))
    source_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    ownership: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[ProcessingJobRecord] = relationship(
        back_populates="capture",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ProcessingJobRecord(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (Index("ix_processing_jobs_state_updated", "state", "updated_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    capture_id: Mapped[UUID] = mapped_column(
        ForeignKey("captures.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    capture: Mapped[CaptureRecord] = relationship(back_populates="job")
