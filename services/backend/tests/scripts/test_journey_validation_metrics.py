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
    pain_score: int,
    complete_plan: bool,
    offer_outcome: str = "declined",
    payment_evidence: str = "none",
    execution_outcome: str = "not_executed",
    maturity_reached: bool = True,
    trip_days: int = 4,
    offer_amount_cny: int = 12,
) -> dict[str, object]:
    trip_start = date(2026, 8, 10) + timedelta(days=index)
    trip_end = trip_start + timedelta(days=trip_days - 1)
    return {
        "participant_id": f"m0-p{index:03d}",
        "recruiting_source": "xiaohongshu_dm",
        "qualified_icp": True,
        "trip_template": "travel_3_7_day",
        "trip_start": trip_start.isoformat(),
        "trip_end": trip_end.isoformat(),
        "trip_days": trip_days,
        "trip_within_30_days": True,
        "pain_question_completed": True,
        "pain_score": pain_score,
        "current_workaround": "manual_notes_and_saved_posts",
        "cost_of_failure": "overpacking_or_buying_emergency_items",
        "evidence_of_action": ["saved_inspiration", "started_packing_list"],
        "wardrobe_import_tolerance": {
            "accepted_minimum_slot_coverage": True,
            "accepted_item_count": 12,
        },
        "complete_plan_delivered": complete_plan,
        "offer": {
            "shown": complete_plan,
            "amount_cny": offer_amount_cny,
            "currency": "CNY",
            "outcome": offer_outcome,
            "real_payment_evidence": payment_evidence,
        },
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
        "post_trip": {
            "maturity_reached": maturity_reached,
            "trip_end_plus_7": (trip_end + timedelta(days=7)).isoformat(),
            "followed_up": execution_outcome != "non_response",
            "execution_outcome": execution_outcome,
        },
        "exclusions": [],
    }


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
                offer_outcome="paid" if index < 5 else "declined",
                payment_evidence="verified_deposit" if index < 5 else "none",
                execution_outcome=(
                    "planned_main_or_alternative" if index < 8 else "non_response"
                ),
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
    assert metrics["maturity_cutoff"] == "2026-09-03"
    assert metrics["all_m0_thresholds_passed"] is True


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


def test_validate_rejects_contact_details_in_deidentified_records(tmp_path: Path) -> None:
    record = _record(0, pain_score=8, complete_plan=True)
    record["current_workaround"] = "email me at buyer@example.com"
    payload = tmp_path / "pii.json"
    payload.write_text(json.dumps(_cohort([record])), encoding="utf-8")

    result = _run_validate(payload)

    assert result.returncode == 1
    assert "possible PII/contact detail" in result.stderr
