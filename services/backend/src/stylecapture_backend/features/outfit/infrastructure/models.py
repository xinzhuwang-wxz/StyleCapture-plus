from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stylecapture_backend.platform.database import Base


class PurchaseDemandRecord(Base):
    __tablename__ = "outfit_purchase_demands"
    __table_args__ = (
        CheckConstraint(
            "role IN ('tops','bottoms','dresses','outerwear','shoes','accessories')",
            name="outfit_purchase_demand_role",
        ),
        CheckConstraint(
            "status IN ('wanted','purchased_pending','owned')",
            name="outfit_purchase_demand_status",
        ),
        Index(
            "ix_outfit_purchase_demands_user_look",
            "user_id",
            "look_id",
        ),
        UniqueConstraint(
            "look_id",
            "role",
            name="uq_outfit_purchase_demands_look_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    look_id: Mapped[UUID] = mapped_column(
        ForeignKey("looks.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"),
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    search_query: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutfitWorkflowTraceRecord(Base):
    __tablename__ = "outfit_workflow_traces"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidates_ready','completed','degraded')",
            name="outfit_workflow_trace_status",
        ),
        Index(
            "ix_outfit_workflow_traces_user_updated",
            "user_id",
            "updated_at",
        ),
        UniqueConstraint(
            "user_id",
            "request_id",
            name="uq_outfit_workflow_traces_user_request",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation_state: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_count: Mapped[int] = mapped_column(Integer, nullable=False)
    capability_alias: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
