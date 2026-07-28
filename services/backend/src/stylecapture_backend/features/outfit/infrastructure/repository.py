from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.account.infrastructure.repository import (
    SqlAlchemyAccountRepository,
)
from stylecapture_backend.features.account.ports import SubjectWriteLease
from stylecapture_backend.features.capture.domain import OwnershipState
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitWorkflowStatus,
    OutfitWorkflowTrace,
    PurchaseDemand,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.infrastructure.models import (
    OutfitWorkflowTraceRecord,
    PurchaseDemandRecord,
)
from stylecapture_backend.features.outfit.ports import OutfitPostSaveUnavailable
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)

PURCHASE_NAMESPACE = UUID("de4ebf5b-dc5e-453b-bd99-9cbb2796621a")


class SqlAlchemyOutfitWorkflowTraceRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        subject_writes: SubjectWriteLease | None = None,
    ) -> None:
        self._sessions = sessions
        self._subject_writes = subject_writes or SqlAlchemyAccountRepository(sessions)

    async def save(self, trace: OutfitWorkflowTrace) -> OutfitWorkflowTrace:
        async with self._subject_writes.subject_write(trace.user_id) as canonical:
            canonical_trace = (
                trace if trace.user_id == canonical else replace(trace, user_id=canonical)
            )
            return await self._save(canonical_trace)

    async def _save(self, trace: OutfitWorkflowTrace) -> OutfitWorkflowTrace:
        async with self._sessions() as session:
            statement = (
                insert(OutfitWorkflowTraceRecord)
                .values(
                    id=trace.id,
                    user_id=trace.user_id,
                    request_id=trace.request_id,
                    status=trace.status.value,
                    explanation_state=trace.explanation_state,
                    plan_count=trace.plan_count,
                    capability_alias=trace.capability_alias,
                    model_version=trace.model_version,
                    created_at=trace.created_at,
                    updated_at=trace.updated_at,
                )
                .on_conflict_do_update(
                    constraint="uq_outfit_workflow_traces_user_request",
                    set_={
                        "status": trace.status.value,
                        "explanation_state": trace.explanation_state,
                        "plan_count": trace.plan_count,
                        "capability_alias": trace.capability_alias,
                        "model_version": trace.model_version,
                        "updated_at": trace.updated_at,
                    },
                )
            )
            await session.execute(statement)
            await session.commit()
        stored = await self.get_for_user(trace_id=trace.id, user_id=trace.user_id)
        if stored is None:
            raise RuntimeError("saved outfit workflow trace could not be reloaded")
        return stored

    async def get_for_user(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> OutfitWorkflowTrace | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(OutfitWorkflowTraceRecord).where(
                        OutfitWorkflowTraceRecord.id == trace_id,
                        OutfitWorkflowTraceRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            return _trace_from_record(record) if record is not None else None


class SqlAlchemyPurchaseDemandRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        wardrobe: SqlAlchemyWardrobeRepository | None = None,
        subject_writes: SubjectWriteLease | None = None,
    ) -> None:
        self._sessions = sessions
        self._subject_writes = subject_writes or SqlAlchemyAccountRepository(sessions)
        self._wardrobe = wardrobe or SqlAlchemyWardrobeRepository(
            sessions,
            subject_writes=self._subject_writes,
        )

    async def ensure_for_plan(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
        plan: OutfitPlan,
    ) -> tuple[PurchaseDemand, ...]:
        try:
            async with self._subject_writes.subject_write(user_id) as canonical:
                return await self._ensure_for_plan(
                    user_id=canonical,
                    look_id=look_id,
                    plan=plan,
                )
        except OperationalError as error:
            raise OutfitPostSaveUnavailable(
                "purchase demand persistence is temporarily unavailable"
            ) from error

    async def _ensure_for_plan(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
        plan: OutfitPlan,
    ) -> tuple[PurchaseDemand, ...]:
        try:
            purchase_slots = tuple(
                slot for slot in plan.slots if slot.purchase_search_query is not None
            )
            async with self._sessions() as session:
                for slot in purchase_slots:
                    search_query = slot.purchase_search_query
                    assert search_query is not None
                    demand = PurchaseDemand.wanted(
                        id=uuid5(
                            PURCHASE_NAMESPACE,
                            f"purchase:{look_id}:{slot.role.value}",
                        ),
                        user_id=user_id,
                        look_id=look_id,
                        role=slot.role,
                        search_query=search_query,
                        item_id=slot.purchase_item_id,
                    )
                    statement = (
                        insert(PurchaseDemandRecord)
                        .values(
                            id=demand.id,
                            user_id=demand.user_id,
                            look_id=demand.look_id,
                            item_id=demand.item_id,
                            role=demand.role.value,
                            search_query=demand.search_query,
                            status=demand.status.value,
                            created_at=demand.created_at,
                            updated_at=demand.updated_at,
                        )
                        .on_conflict_do_update(
                            constraint="uq_outfit_purchase_demands_look_role",
                            set_={
                                "search_query": demand.search_query,
                                "item_id": demand.item_id,
                                "updated_at": demand.updated_at,
                            },
                        )
                    )
                    await session.execute(statement)
                await session.commit()
            return await self.list_for_look(user_id=user_id, look_id=look_id)
        except OperationalError as error:
            raise OutfitPostSaveUnavailable(
                "purchase demand persistence is temporarily unavailable"
            ) from error

    async def list_for_look(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> tuple[PurchaseDemand, ...]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(PurchaseDemandRecord)
                    .where(
                        PurchaseDemandRecord.user_id == user_id,
                        PurchaseDemandRecord.look_id == look_id,
                    )
                    .order_by(PurchaseDemandRecord.created_at, PurchaseDemandRecord.role)
                )
            ).scalars()
            return tuple(_from_record(row) for row in rows)

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
    ) -> PurchaseDemand | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(PurchaseDemandRecord).where(
                        PurchaseDemandRecord.id == demand_id,
                        PurchaseDemandRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            return _from_record(record) if record is not None else None

    async def advance(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
        target: PurchaseDemandStatus,
    ) -> PurchaseDemand:
        async with self._subject_writes.subject_write(user_id) as canonical:
            return await self._advance(
                user_id=canonical,
                demand_id=demand_id,
                target=target,
            )

    async def _advance(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
        target: PurchaseDemandStatus,
    ) -> PurchaseDemand:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(PurchaseDemandRecord)
                    .where(
                        PurchaseDemandRecord.id == demand_id,
                        PurchaseDemandRecord.user_id == user_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if record is None:
                raise LookupError(demand_id)
            current = _from_record(record)
            advanced = current.advance(target)
            if advanced.status is PurchaseDemandStatus.OWNED and advanced.item_id is not None:
                updated = await self._wardrobe.set_ownership_in_transaction(
                    session,
                    user_id=user_id,
                    item_id=advanced.item_id,
                    ownership=OwnershipState.OWNED,
                    updated_at=advanced.updated_at,
                )
                if not updated:
                    raise ValueError("linked wardrobe item is unavailable for ownership update")
            record.status = advanced.status.value
            record.updated_at = advanced.updated_at
            await session.commit()
        stored = await self.get_for_user(
            user_id=user_id,
            demand_id=demand_id,
        )
        if stored is None:
            raise RuntimeError("saved purchase demand could not be reloaded")
        return stored


def _from_record(record: PurchaseDemandRecord) -> PurchaseDemand:
    return PurchaseDemand(
        id=record.id,
        user_id=record.user_id,
        look_id=record.look_id,
        item_id=record.item_id,
        role=OutfitCategory(record.role),
        search_query=record.search_query,
        status=PurchaseDemandStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _trace_from_record(record: OutfitWorkflowTraceRecord) -> OutfitWorkflowTrace:
    return OutfitWorkflowTrace(
        id=record.id,
        user_id=record.user_id,
        request_id=record.request_id,
        status=OutfitWorkflowStatus(record.status),
        explanation_state=record.explanation_state,
        plan_count=record.plan_count,
        capability_alias=record.capability_alias,
        model_version=record.model_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
