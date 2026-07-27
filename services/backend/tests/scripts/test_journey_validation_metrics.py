from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPOSITORY_ROOT / "scripts" / "journey_validation_metrics.py"
SCHEMA = REPOSITORY_ROOT / "docs" / "research" / "journey-validation" / "metrics.schema.json"


def _record(
    index: int,
    *,
    pain_score: int | None,
    complete_plan: bool,
    pain_question_completed: bool = True,
    source_bucket: str = "natural_search_public_intent",
    professional_creator: bool = False,
    offer_outcome: str = "declined",
    payment_evidence: str = "none",
    execution_outcome: str = "not_executed",
    maturity_reached: bool = True,
    trip_days: int = 4,
    offer_amount_cny: int = 12,
    include_pain_score: bool = True,
    offer_evidence_ref: str | None = None,
    post_trip_evidence_ref: str | None = None,
) -> dict[str, object]:
    trip_start = date(2026, 8, 10) + timedelta(days=index)
    trip_end = trip_start + timedelta(days=trip_days - 1)
    offer: dict[str, object] = {
        "shown": complete_plan,
        "amount_cny": offer_amount_cny,
        "currency": "CNY",
        "outcome": offer_outcome,
        "real_payment_evidence": payment_evidence,
    }
    if offer_evidence_ref is not None:
        offer["evidence_ref"] = offer_evidence_ref

    post_trip: dict[str, object] = {
        "maturity_reached": maturity_reached,
        "trip_end_plus_7": (trip_end + timedelta(days=7)).isoformat(),
        "followed_up": execution_outcome != "non_response",
        "execution_outcome": execution_outcome,
    }
    if post_trip_evidence_ref is not None:
        post_trip["evidence_ref"] = post_trip_evidence_ref

    record: dict[str, object] = {
        "participant_id": f"m0-p{index:03d}",
        "recruiting_source": "xiaohongshu_dm",
        "source_bucket": source_bucket,
        "professional_creator": professional_creator,
        "qualified_icp": True,
        "trip_template": "travel_3_7_day",
        "trip_start": trip_start.isoformat(),
        "trip_end": trip_end.isoformat(),
        "trip_days": trip_days,
        "trip_within_30_days": True,
        "pain_question_completed": pain_question_completed,
        "current_workaround": "manual_notes_and_saved_posts",
        "cost_of_failure": "overpacking_or_buying_emergency_items",
        "evidence_of_action": ["saved_inspiration", "started_packing_list"],
        "wardrobe_import_tolerance": {
            "accepted_minimum_slot_coverage": True,
            "accepted_item_count": 12,
        },
        "complete_plan_delivered": complete_plan,
        "offer": offer,
        "pixel_world_primed": False,
        "plan": {
            "constraints_confirmed": complete_plan,
            "selected_garments_count": 12 if complete_plan else 0,
            "day_activity_looks_count": trip_days if complete_plan else 0,
            "alternatives_count": trip_days if complete_plan else 0,
            "packing_deduplicated": complete_plan,
            "gaps_recorded": complete_plan,
            "user_corrections_recorded": complete_plan,
            "post_trip_outcome_recorded": maturity_reached,
        },
        "post_trip": post_trip,
        "exclusions": [],
    }
    if include_pain_score:
        record["pain_score"] = pain_score
    return record


def _cohort(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "cohort_id": "m0-2026-08-travel",
        "frozen_at": "2026-09-30T10:00:00+08:00",
        "records": records,
    }


def _run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "validate", str(path), "--schema", str(SCHEMA)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_validate_recomputes_m0_thresholds_from_deidentified_records(tmp_path: Path) -> None:
    records: list[dict[str, object]] = []
    for index in range(20):
        complete_plan = index < 15
        records.append(
            _record(
                index,
                pain_score=7 if index < 12 else 6,
                complete_plan=complete_plan,
                source_bucket=(
                    "natural_search_public_intent"
                    if index < 10
                    else "approved_women_travel_group"
                    if index < 17
                    else "second_degree_referral"
                ),
                offer_outcome="paid" if index < 5 else "declined",
                payment_evidence="verified_deposit" if index < 5 else "none",
                offer_evidence_ref=f"payment/deposit-hash-{index:03d}" if index < 5 else None,
                execution_outcome=("planned_main_or_alternative" if index < 8 else "non_response"),
                post_trip_evidence_ref=f"post-trip/adoption-hash-{index:03d}"
                if index < 8
                else None,
            )
        )
    payload = tmp_path / "m0.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["pain_rate"] == {
        "numerator": 12,
        "denominator": 20,
        "rate": 0.6,
        "passed": True,
    }
    assert metrics["real_paid_rate"] == {
        "numerator": 5,
        "denominator": 15,
        "rate": 0.333333,
        "payer_count": 5,
        "passed": True,
    }
    assert metrics["execution_rate"] == {
        "numerator": 8,
        "denominator": 15,
        "rate": 0.533333,
        "passed": True,
    }
    assert metrics["channel_mix"] == {
        "approved_women_travel_group": {
            "denominator": 20,
            "limit": 0.35,
            "passed": True,
            "rate": 0.35,
            "recruits": 7,
        },
        "natural_search_public_intent": {
            "denominator": 20,
            "limit": 0.5,
            "passed": True,
            "rate": 0.5,
            "recruits": 10,
        },
        "professional_creator": {
            "denominator": 20,
            "limit": 0.2,
            "passed": True,
            "rate": 0.0,
            "recruits": 0,
        },
        "second_degree_referral": {
            "denominator": 20,
            "limit": 0.25,
            "passed": True,
            "rate": 0.15,
            "recruits": 3,
        },
    }
    assert metrics["maturity_cutoff"] == "2026-09-30"
    assert metrics["all_m0_thresholds_passed"] is True


def test_validate_excludes_skipped_pain_question_when_score_is_omitted(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            0,
            pain_score=None,
            complete_plan=False,
            pain_question_completed=False,
            include_pain_score=False,
        ),
        _record(1, pain_score=8, complete_plan=False),
    ]
    payload = tmp_path / "skipped-pain-omitted.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["pain_rate"]["numerator"] == 1
    assert metrics["pain_rate"]["denominator"] == 1


def test_validate_requires_pain_score_when_completed_question_omits_score(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "completed-pain-omitted.json"
    payload.write_text(
        json.dumps(
            _cohort(
                [
                    _record(
                        0,
                        pain_score=None,
                        complete_plan=False,
                        include_pain_score=False,
                    )
                ]
            )
        ),
        encoding="utf-8",
    )

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "pain_score is required when pain question is completed" in result.stderr


def test_validate_rejects_non_travel_or_single_day_cohort_members(tmp_path: Path) -> None:
    payload = tmp_path / "single-day.json"
    payload.write_text(
        json.dumps(_cohort([_record(0, pain_score=8, complete_plan=True, trip_days=1)])),
        encoding="utf-8",
    )

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "trip_days must be between 3 and 7" in result.stderr


def test_validate_requires_one_cny12_offer_for_complete_plan_recipients(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "wrong-offer.json"
    payload.write_text(
        json.dumps(_cohort([_record(0, pain_score=8, complete_plan=True, offer_amount_cny=18)])),
        encoding="utf-8",
    )

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "complete plan recipients must be shown exactly one CNY 12 offer" in result.stderr


def test_validate_excludes_promises_from_real_paid_and_counts_nonresponse_as_not_executed(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            index,
            pain_score=8,
            complete_plan=True,
            offer_outcome="paid" if index < 5 else "declined",
            payment_evidence="oral_promise" if index < 5 else "none",
            execution_outcome="non_response",
        )
        for index in range(15)
    ]
    payload = tmp_path / "promises.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["real_paid_rate"]["numerator"] == 0
    assert metrics["real_paid_rate"]["passed"] is False
    assert metrics["execution_rate"]["numerator"] == 0
    assert metrics["execution_rate"]["denominator"] == 15


def test_validate_requires_payment_evidence_ref_for_verified_real_payment(
    tmp_path: Path,
) -> None:
    record = _record(
        0,
        pain_score=8,
        complete_plan=True,
        offer_outcome="paid",
        payment_evidence="verified_payment",
    )
    payload = tmp_path / "missing-payment-evidence-ref.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "offer.evidence_ref is required for verified payment evidence" in result.stderr


def test_validate_accepts_verified_real_payment_with_external_evidence_ref(
    tmp_path: Path,
) -> None:
    record = _record(
        0,
        pain_score=8,
        complete_plan=True,
        offer_outcome="paid",
        payment_evidence="verified_deposit",
        offer_evidence_ref="payment/deposit-hash-001",
    )
    payload = tmp_path / "payment-evidence-ref.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr


def test_validate_requires_post_trip_evidence_ref_for_successful_execution(
    tmp_path: Path,
) -> None:
    record = _record(
        0,
        pain_score=8,
        complete_plan=True,
        execution_outcome="planned_main_or_alternative",
    )
    payload = tmp_path / "missing-execution-evidence-ref.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "post_trip.evidence_ref is required for successful execution outcome" in result.stderr


def test_validate_accepts_successful_execution_with_external_evidence_ref(
    tmp_path: Path,
) -> None:
    record = _record(
        0,
        pain_score=8,
        complete_plan=True,
        execution_outcome="hard_constraint_preserving_replacement",
        post_trip_evidence_ref="post-trip/adoption-hash-001",
    )
    payload = tmp_path / "execution-evidence-ref.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr


def test_validate_derives_maturity_from_frozen_cutoff_and_rejects_future_maturity(
    tmp_path: Path,
) -> None:
    record = _record(0, pain_score=8, complete_plan=True, maturity_reached=True)
    payload = _cohort([record])
    payload["frozen_at"] = "2026-08-15T10:00:00+08:00"
    aggregate = tmp_path / "future-maturity.json"
    aggregate.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_validate(aggregate)

    assert result.returncode == 1
    assert "maturity_reached contradicts frozen_at cutoff" in result.stderr


def test_validate_includes_elapsed_cutoff_nonresponders_in_execution_denominator(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            index,
            pain_score=8,
            complete_plan=True,
            maturity_reached=True,
            execution_outcome="non_response",
        )
        for index in range(15)
    ]
    payload = _cohort(records)
    payload["frozen_at"] = "2026-09-30T10:00:00+08:00"
    aggregate = tmp_path / "elapsed-nonresponse.json"
    aggregate.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_validate(aggregate)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["execution_rate"]["denominator"] == 15
    assert metrics["execution_rate"]["numerator"] == 0


def test_validate_excludes_skipped_pain_question_without_imputed_score(tmp_path: Path) -> None:
    records = [
        _record(0, pain_score=None, pain_question_completed=False, complete_plan=False),
        _record(1, pain_score=8, complete_plan=False),
    ]
    payload = tmp_path / "skipped-pain.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["pain_rate"]["denominator"] == 1
    assert metrics["pain_rate"]["numerator"] == 1


def test_validate_rejects_imputed_pain_score_when_question_was_skipped(
    tmp_path: Path,
) -> None:
    record = _record(0, pain_score=7, pain_question_completed=False, complete_plan=False)
    payload = tmp_path / "imputed-pain.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "pain_score must be null when pain question is skipped" in result.stderr


def test_validate_rejects_recruiting_channel_cap_overage(tmp_path: Path) -> None:
    records = [
        _record(
            index,
            pain_score=8,
            complete_plan=False,
            source_bucket=(
                "natural_search_public_intent" if index < 11 else "approved_women_travel_group"
            ),
        )
        for index in range(20)
    ]
    payload = tmp_path / "source-cap.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "source bucket natural_search_public_intent exceeds cap 0.5" in result.stderr


def test_validate_rejects_professional_creator_cap_overage(tmp_path: Path) -> None:
    source_buckets = (
        ["natural_search_public_intent"] * 10
        + ["approved_women_travel_group"] * 8
        + ["second_degree_referral"] * 6
        + ["other"]
    )
    records = [
        _record(
            index,
            pain_score=8,
            complete_plan=False,
            source_bucket=source_buckets[index],
            professional_creator=index < 6,
        )
        for index in range(25)
    ]
    payload = tmp_path / "creator-cap.json"
    payload.write_text(json.dumps(_cohort(records)), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "professional_creator exceeds cap 0.2" in result.stderr


def test_validate_rejects_contact_details_in_deidentified_records(tmp_path: Path) -> None:
    record = _record(0, pain_score=8, complete_plan=True)
    record["current_workaround"] = "email me at buyer@example.com"
    payload = tmp_path / "pii.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "possible PII/contact detail" in result.stderr
