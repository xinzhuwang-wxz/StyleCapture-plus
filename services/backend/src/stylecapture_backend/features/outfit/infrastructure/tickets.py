from __future__ import annotations

import base64
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitReasoningTrace,
    OutfitRequest,
    OutfitSlot,
)


class InvalidOutfitPlanTicket(ValueError):
    """The plan ticket is invalid, expired, or belongs to another user."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class OutfitPlanTicketSigner:
    def __init__(
        self,
        secret: str,
        *,
        now: Callable[[], datetime] | None = None,
        lifetime: timedelta = timedelta(minutes=30),
    ) -> None:
        if len(secret) < 24:
            raise ValueError("outfit plan signing secret must be at least 24 characters")
        if lifetime <= timedelta(0):
            raise ValueError("outfit plan ticket lifetime must be positive")
        self._secret = secret.encode("utf-8")
        self._now = now or (lambda: datetime.now(UTC))
        self._lifetime = lifetime

    def issue(
        self,
        *,
        user_id: UUID,
        plan: OutfitPlan,
        explanation_state: str,
        request: OutfitRequest,
        reasoning_trace: OutfitReasoningTrace | None = None,
    ) -> str:
        payload = {
            "expires_at": int((self._aware_now() + self._lifetime).timestamp()),
            "explanation_state": explanation_state,
            "plan": {
                "id": str(plan.id),
                "rationale": plan.rationale,
                "scene": plan.scene,
                "slots": [
                    {
                        "image_url": slot.image_url,
                        "item_id": str(slot.item_id) if slot.item_id is not None else None,
                        "item_name": slot.item_name,
                        "ownership": slot.ownership,
                        "role": slot.role.value,
                        "search_query": slot.search_query,
                        "source_kind": slot.source_kind,
                    }
                    for slot in plan.slots
                ],
                "style_match_score": plan.style_match_score,
                "title": plan.title,
            },
            "request": {
                "anchor_item_id": (
                    str(request.anchor_item_id) if request.anchor_item_id is not None else None
                ),
                "comfort": request.comfort,
                "exclude_item_ids": [str(item_id) for item_id in request.exclude_item_ids],
                "formality": request.formality,
                "must_include_item_ids": [
                    str(item_id) for item_id in request.must_include_item_ids
                ],
                "plan_count": request.plan_count,
                "scene": request.scene,
                "style": request.style,
                "weather": request.weather,
            },
            "reasoning_trace": (
                {
                    "capability_alias": reasoning_trace.capability_alias,
                    "latency_ms": reasoning_trace.latency_ms,
                    "model_version": reasoning_trace.model_version,
                    "prompt_version": reasoning_trace.prompt_version,
                    "schema_version": reasoning_trace.schema_version,
                }
                if reasoning_trace is not None
                else None
            ),
            "user_id": str(user_id),
            "version": 3,
        }
        encoded = _encode(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        signature = _encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
        return f"{encoded}.{signature}"

    def verify(
        self,
        token: str,
        *,
        user_id: UUID,
        expected_plan_id: UUID,
    ) -> tuple[OutfitPlan, str, OutfitRequest, OutfitReasoningTrace | None]:
        try:
            encoded, supplied_signature = token.split(".", maxsplit=1)
            expected_signature = _encode(
                hmac.digest(self._secret, encoded.encode("ascii"), "sha256")
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature mismatch")
            payload = json.loads(_decode(encoded))
            if set(payload) != {
                "expires_at",
                "explanation_state",
                "plan",
                "reasoning_trace",
                "request",
                "user_id",
                "version",
            }:
                raise ValueError("unexpected ticket fields")
            if payload["version"] != 3 or UUID(str(payload["user_id"])) != user_id:
                raise ValueError("ticket principal mismatch")
            if self._aware_now() >= datetime.fromtimestamp(
                int(payload["expires_at"]),
                tz=UTC,
            ):
                raise ValueError("ticket expired")
            plan_payload = payload["plan"]
            plan = OutfitPlan(
                id=UUID(str(plan_payload["id"])),
                title=str(plan_payload["title"]),
                scene=str(plan_payload["scene"]),
                slots=tuple(
                    OutfitSlot(
                        role=OutfitCategory(str(slot["role"])),
                        item_id=(
                            UUID(str(slot["item_id"])) if slot["item_id"] is not None else None
                        ),
                        item_name=slot["item_name"],
                        ownership=slot["ownership"],
                        image_url=slot["image_url"],
                        search_query=slot["search_query"],
                        source_kind=slot["source_kind"],
                    )
                    for slot in plan_payload["slots"]
                ),
                rationale=str(plan_payload["rationale"]),
                style_match_score=int(plan_payload["style_match_score"]),
            )
            request_payload = payload["request"]
            request = OutfitRequest(
                scene=str(request_payload["scene"]),
                style=request_payload["style"],
                weather=request_payload["weather"],
                formality=request_payload["formality"],
                comfort=request_payload["comfort"],
                plan_count=int(request_payload.get("plan_count", 4)),
                anchor_item_id=(
                    UUID(str(request_payload["anchor_item_id"]))
                    if request_payload["anchor_item_id"] is not None
                    else None
                ),
                must_include_item_ids=tuple(
                    UUID(str(item_id)) for item_id in request_payload["must_include_item_ids"]
                ),
                exclude_item_ids=tuple(
                    UUID(str(item_id)) for item_id in request_payload["exclude_item_ids"]
                ),
            )
            explanation_state = str(payload["explanation_state"])
            trace_payload = payload["reasoning_trace"]
            reasoning_trace = (
                OutfitReasoningTrace(
                    capability_alias=str(trace_payload["capability_alias"]),
                    model_version=str(trace_payload["model_version"]),
                    prompt_version=str(trace_payload["prompt_version"]),
                    schema_version=str(trace_payload["schema_version"]),
                    latency_ms=int(trace_payload["latency_ms"]),
                )
                if trace_payload is not None
                else None
            )
            if plan.id != expected_plan_id or explanation_state not in {
                "llm_ranked",
                "rule_ranked",
            }:
                raise ValueError("ticket semantics mismatch")
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise InvalidOutfitPlanTicket("穿搭方案已失效, 请重新生成") from error
        return plan, explanation_state, request, reasoning_trace

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("outfit plan ticket clock must be timezone-aware")
        return value.astimezone(UTC)
