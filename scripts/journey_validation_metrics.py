#!/usr/bin/env python3
"""Validate and recompute StyleCapture Journey M0 research metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

PAIN_THRESHOLD = 7
MIN_PAIN_DENOMINATOR = 20
MIN_PLAN_RECIPIENT_DENOMINATOR = 15
MIN_PAIN_RATE = 0.60
MIN_REAL_PAID_RATE = 0.33
MIN_PAYER_COUNT = 5
MIN_EXECUTION_RATE = 0.50
OFFER_AMOUNT_CNY = 12
TRIP_TEMPLATE = "travel_3_7_day"
REAL_PAYMENT_EVIDENCE = {"verified_payment", "verified_deposit"}
EXECUTED_OUTCOMES = {
    "planned_main_or_alternative",
    "hard_constraint_preserving_replacement",
}
SOURCE_CAPS = {
    "natural_search_public_intent": 0.50,
    "approved_women_travel_group": 0.35,
    "second_degree_referral": 0.25,
}
PROFESSIONAL_CREATOR_CAP = 0.20
CONTACT_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?:wechat|weixin|微信|手机号|电话|phone)\s*[:\uff1a]", re.IGNORECASE),
)


class ValidationFailure(ValueError):
    pass


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _validate_schema(payload: Any, schema: Any) -> None:
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.path) or "<root>"
        raise ValidationFailure(f"schema violation at {path}: {error.message}")


def _iter_strings(value: Any, path: str = "<root>") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _iter_strings(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _iter_strings(nested, f"{path}[{index}]")


def _scan_for_contact_details(payload: Any) -> None:
    for path, value in _iter_strings(payload):
        for pattern in CONTACT_PATTERNS:
            if pattern.search(value):
                raise ValidationFailure(f"possible PII/contact detail at {path}")


def _parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationFailure(f"{field} must be an ISO date") from exc


def _parse_frozen_date(value: str) -> date:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValidationFailure("frozen_at must be an ISO datetime") from exc


def _trip_end_plus_7(record: Mapping[str, Any]) -> date:
    return _parse_date(record["trip_end"], field="trip_end") + timedelta(days=7)


def _validate_record(record: Mapping[str, Any], *, frozen_date: date) -> None:
    participant_id = record["participant_id"]
    if record["trip_template"] != TRIP_TEMPLATE:
        raise ValidationFailure(f"{participant_id}: trip_template must be {TRIP_TEMPLATE}")
    if not 3 <= record["trip_days"] <= 7:
        raise ValidationFailure(f"{participant_id}: trip_days must be between 3 and 7")
    if not record["trip_within_30_days"]:
        raise ValidationFailure(f"{participant_id}: trip must be within 30 days")
    if record["pixel_world_primed"]:
        raise ValidationFailure(f"{participant_id}: pixel_world_primed must be false for M0")
    has_pain_score = "pain_score" in record
    pain_score = record.get("pain_score")
    if record["pain_question_completed"] and pain_score is None:
        raise ValidationFailure(f"{participant_id}: pain_score is required when pain question is completed")
    if not record["pain_question_completed"] and has_pain_score and pain_score is not None:
        raise ValidationFailure(f"{participant_id}: pain_score must be null when pain question is skipped")

    trip_start = _parse_date(record["trip_start"], field="trip_start")
    trip_end = _parse_date(record["trip_end"], field="trip_end")
    if (trip_end - trip_start).days + 1 != record["trip_days"]:
        raise ValidationFailure(f"{participant_id}: trip_days must match trip_start/trip_end")

    if record["complete_plan_delivered"]:
        offer = record["offer"]
        if (
            not offer["shown"]
            or offer["amount_cny"] != OFFER_AMOUNT_CNY
            or offer["currency"] != "CNY"
        ):
            raise ValidationFailure(
                f"{participant_id}: complete plan recipients must be shown exactly one CNY 12 offer"
            )
        plan = record["plan"]
        required_flags = (
            "constraints_confirmed",
            "packing_deduplicated",
            "gaps_recorded",
            "user_corrections_recorded",
        )
        missing_flags = [field for field in required_flags if not plan[field]]
        if missing_flags:
            raise ValidationFailure(
                f"{participant_id}: complete plan is missing {', '.join(missing_flags)}"
            )
        if plan["selected_garments_count"] < 8:
            raise ValidationFailure(f"{participant_id}: complete plan needs at least 8 garments")
        if plan["day_activity_looks_count"] < record["trip_days"]:
            raise ValidationFailure(f"{participant_id}: complete plan needs a look for every trip day")
        if plan["alternatives_count"] < record["trip_days"]:
            raise ValidationFailure(f"{participant_id}: complete plan needs an alternative for every trip day")

    expected_maturity_date = trip_end + timedelta(days=7)
    actual_maturity_date = _parse_date(record["post_trip"]["trip_end_plus_7"], field="trip_end_plus_7")
    if actual_maturity_date != expected_maturity_date:
        raise ValidationFailure(f"{participant_id}: trip_end_plus_7 must equal trip_end + 7d")

    derived_mature = expected_maturity_date <= frozen_date
    if record["post_trip"]["maturity_reached"] != derived_mature:
        raise ValidationFailure(f"{participant_id}: maturity_reached contradicts frozen_at cutoff")
    execution_outcome = record["post_trip"]["execution_outcome"]
    if derived_mature and execution_outcome == "not_mature":
        raise ValidationFailure(f"{participant_id}: execution_outcome cannot be not_mature after cutoff")
    if not derived_mature and execution_outcome != "not_mature":
        raise ValidationFailure(f"{participant_id}: execution_outcome must be not_mature before cutoff")


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _metric(numerator: int, denominator: int, *, min_denominator: int, min_rate: float) -> dict[str, Any]:
    rate = _rate(numerator, denominator)
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": rate,
        "passed": denominator >= min_denominator and rate is not None and rate >= min_rate,
    }


def _rate_metric(count: int, denominator: int, limit: float) -> dict[str, Any]:
    rate = _rate(count, denominator)
    enforce_cap = denominator >= MIN_PAIN_DENOMINATOR
    return {
        "recruits": count,
        "denominator": denominator,
        "rate": rate,
        "limit": limit,
        "passed": not enforce_cap or (rate is not None and rate <= limit),
    }


def _channel_mix(qualified_records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    denominator = len(qualified_records)
    mix: dict[str, dict[str, Any]] = {}
    professional_creator_count = sum(1 for record in qualified_records if record["professional_creator"])
    mix["professional_creator"] = _rate_metric(
        professional_creator_count,
        denominator,
        PROFESSIONAL_CREATOR_CAP,
    )
    if not mix["professional_creator"]["passed"]:
        raise ValidationFailure(f"professional_creator exceeds cap {PROFESSIONAL_CREATOR_CAP}")

    for source_bucket, cap in SOURCE_CAPS.items():
        count = sum(1 for record in qualified_records if record["source_bucket"] == source_bucket)
        mix[source_bucket] = _rate_metric(count, denominator, cap)
        if not mix[source_bucket]["passed"]:
            raise ValidationFailure(f"source bucket {source_bucket} exceeds cap {cap}")
    return mix


def recompute(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = payload["records"]
    frozen_date = _parse_frozen_date(payload["frozen_at"])
    participant_ids = [record["participant_id"] for record in records]
    if len(participant_ids) != len(set(participant_ids)):
        raise ValidationFailure("participant_id values must be unique")
    for record in records:
        _validate_record(record, frozen_date=frozen_date)

    qualified_records = [record for record in records if record["qualified_icp"]]
    channel_mix = _channel_mix(qualified_records)

    pain_denominator = sum(
        1
        for record in records
        if record["qualified_icp"] and record["pain_question_completed"]
    )
    pain_numerator = sum(
        1
        for record in records
        if record["qualified_icp"]
        and record["pain_question_completed"]
        and (pain_score := record.get("pain_score")) is not None
        and pain_score >= PAIN_THRESHOLD
    )

    plan_recipients = [
        record for record in records if record["qualified_icp"] and record["complete_plan_delivered"]
    ]
    real_paid = [
        record
        for record in plan_recipients
        if record["offer"]["shown"]
        and record["offer"]["amount_cny"] == OFFER_AMOUNT_CNY
        and record["offer"]["currency"] == "CNY"
        and record["offer"]["outcome"] in {"paid", "refunded"}
        and record["offer"]["real_payment_evidence"] in REAL_PAYMENT_EVIDENCE
    ]

    mature_recipients = [
        record for record in plan_recipients if _trip_end_plus_7(record) <= frozen_date
    ]
    executed = [
        record
        for record in mature_recipients
        if record["post_trip"]["execution_outcome"] in EXECUTED_OUTCOMES
    ]
    pain_rate = _metric(
        pain_numerator,
        pain_denominator,
        min_denominator=MIN_PAIN_DENOMINATOR,
        min_rate=MIN_PAIN_RATE,
    )
    real_paid_rate = _metric(
        len(real_paid),
        len(plan_recipients),
        min_denominator=MIN_PLAN_RECIPIENT_DENOMINATOR,
        min_rate=MIN_REAL_PAID_RATE,
    )
    real_paid_rate["payer_count"] = len(real_paid)
    real_paid_rate["passed"] = real_paid_rate["passed"] and len(real_paid) >= MIN_PAYER_COUNT
    execution_rate = _metric(
        len(executed),
        len(mature_recipients),
        min_denominator=MIN_PLAN_RECIPIENT_DENOMINATOR,
        min_rate=MIN_EXECUTION_RATE,
    )

    return {
        "cohort_id": payload["cohort_id"],
        "frozen_at": payload["frozen_at"],
        "channel_mix": channel_mix,
        "pain_rate": pain_rate,
        "real_paid_rate": real_paid_rate,
        "execution_rate": execution_rate,
        "maturity_cutoff": frozen_date.isoformat(),
        "all_m0_thresholds_passed": bool(
            pain_rate["passed"] and real_paid_rate["passed"] and execution_rate["passed"]
        ),
    }


def validate_metrics(payload_path: Path, schema_path: Path) -> dict[str, Any]:
    payload = _load_json(payload_path)
    schema = _load_json(schema_path)
    _validate_schema(payload, schema)
    _scan_for_contact_details(payload)
    return recompute(payload)


def _validate_command(args: argparse.Namespace) -> int:
    try:
        metrics = validate_metrics(args.payload, args.schema)
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError, ValidationFailure) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate records and recompute M0 metrics")
    validate.add_argument("payload", type=Path)
    validate.add_argument(
        "--schema",
        type=Path,
        default=Path("docs/research/journey-validation/metrics.schema.json"),
    )
    validate.set_defaults(func=_validate_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
