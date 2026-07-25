from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stylecapture_backend.platform.database import Base


class LookRecord(Base):
    __tablename__ = "looks"
    __table_args__ = (
        CheckConstraint(
            "source IN ('feed_saved','user_created','ai_generated')",
            name="look_source",
        ),
        CheckConstraint(
            "status IN ('processing','partial','ready','error')",
            name="look_status",
        ),
        CheckConstraint(
            "(source = 'ai_generated' AND capture_id IS NULL) OR "
            "(source <> 'ai_generated' AND capture_id IS NOT NULL)",
            name="look_source_capture_provenance",
        ),
        Index("ix_looks_user_created", "user_id", "created_at"),
        Index("ix_looks_user_status", "user_id", "status"),
        UniqueConstraint(
            "capture_id",
            "source_selection_key",
            name="uq_looks_capture_id_source_selection_key",
        ),
        Index(
            "uq_looks_composition_user_source_selection",
            "user_id",
            "source",
            "source_selection_key",
            unique=True,
            postgresql_where=text("capture_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    capture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("captures.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_selection_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    analysis: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    display_object_key: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LookComponentRecord(Base):
    __tablename__ = "look_components"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','ready','error')",
            name="look_component_status",
        ),
        CheckConstraint(
            "(status = 'ready' AND item_id IS NOT NULL) OR (status <> 'ready' AND item_id IS NULL)",
            name="look_component_ready_item",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="look_component_display_order",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="look_component_confidence",
        ),
        Index("ix_look_components_look_order", "look_id", "display_order"),
        Index(
            "ix_look_components_look_item",
            "look_id",
            "item_id",
            unique=True,
            postgresql_where=text("item_id IS NOT NULL"),
        ),
        UniqueConstraint(
            "look_id",
            "component_key",
            name="uq_look_components_look_id_component_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    look_id: Mapped[UUID] = mapped_column(
        ForeignKey("looks.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    evidence_region: Mapped[list[dict[str, float]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    role: Mapped[str | None] = mapped_column(String(80))
    layer: Mapped[str | None] = mapped_column(String(80))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    grounding_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PreferenceSignalRecord(Base):
    __tablename__ = "preference_signals"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('look_saved','liking_reason_added')",
            name="preference_signal_kind",
        ),
        Index(
            "ix_preference_signals_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_preference_signals_look_created",
            "look_id",
            "created_at",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_preference_signals_user_id_idempotency_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    look_id: Mapped[UUID] = mapped_column(
        ForeignKey("looks.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
