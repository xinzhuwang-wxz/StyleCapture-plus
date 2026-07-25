from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitReasoningTrace,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.features.outfit.infrastructure.tickets import (
    InvalidOutfitPlanTicket,
    OutfitPlanTicketSigner,
)


def plan() -> OutfitPlan:
    return OutfitPlan(
        id=uuid4(),
        title="通勤层次感",
        scene="客户提案",
        slots=(
            OutfitSlot(OutfitCategory.TOP, uuid4(), "白衬衫", "owned", None, None),
            OutfitSlot(OutfitCategory.BOTTOM, uuid4(), "西裤", "owned", None, None),
            OutfitSlot(OutfitCategory.SHOES, uuid4(), "乐福鞋", "owned", None, None),
        ),
        rationale="真实衣橱中的黑白配色形成清晰层次。",
        style_match_score=94,
    )


def test_ticket_round_trips_exact_server_plan_and_rejects_tampering() -> None:
    user_id = uuid4()
    expected = plan()
    signer = OutfitPlanTicketSigner("ticket-signing-secret-with-enough-entropy")
    token = signer.issue(
        user_id=user_id,
        plan=expected,
        explanation_state="llm_ranked",
        request=OutfitRequest(
            scene="客户提案",
            weather="炎热",
            exclude_item_ids=(uuid4(),),
        ),
        reasoning_trace=OutfitReasoningTrace(
            capability_alias="reasoning",
            model_version="doubao-endpoint",
            prompt_version="outfit-rerank-v1",
            schema_version="outfit-rerank-json-v1",
            latency_ms=1234,
        ),
    )

    restored, explanation_state, restored_request, reasoning_trace = signer.verify(
        token,
        user_id=user_id,
        expected_plan_id=expected.id,
    )

    assert restored == expected
    assert explanation_state == "llm_ranked"
    assert restored_request.scene == "客户提案"
    assert restored_request.weather == "炎热"
    assert len(restored_request.exclude_item_ids) == 1
    assert reasoning_trace is not None
    assert reasoning_trace.model_version == "doubao-endpoint"
    assert reasoning_trace.latency_ms == 1234
    with pytest.raises(InvalidOutfitPlanTicket):
        signer.verify(
            f"{token[:-1]}x",
            user_id=user_id,
            expected_plan_id=expected.id,
        )
    with pytest.raises(InvalidOutfitPlanTicket):
        signer.verify(
            token,
            user_id=uuid4(),
            expected_plan_id=expected.id,
        )


def test_ticket_expires() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    expected = plan()
    user_id = uuid4()
    issuer = OutfitPlanTicketSigner(
        "ticket-signing-secret-with-enough-entropy",
        now=lambda: now,
        lifetime=timedelta(minutes=1),
    )
    token = issuer.issue(
        user_id=user_id,
        plan=expected,
        explanation_state="rule_ranked",
        request=OutfitRequest(scene="客户提案"),
    )
    verifier = OutfitPlanTicketSigner(
        "ticket-signing-secret-with-enough-entropy",
        now=lambda: now + timedelta(minutes=2),
    )

    with pytest.raises(InvalidOutfitPlanTicket):
        verifier.verify(
            token,
            user_id=user_id,
            expected_plan_id=expected.id,
        )
