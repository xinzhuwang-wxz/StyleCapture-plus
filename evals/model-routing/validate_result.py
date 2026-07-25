from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _validate(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if payload.get("schema_version") != "stylecapture-model-routing-eval-v1":
        failures.append("unexpected result schema")
    execution = payload.get("execution", {})
    if execution.get("gateway") != "local_litellm":
        failures.append("evaluation did not use the local LiteLLM gateway")
    if execution.get("serial") is not True or execution.get("max_concurrency") != 1:
        failures.append("evaluation was not serial")
    if execution.get("retries") != 0:
        failures.append("evaluation used retries")
    if execution.get("credentials_persisted") is not False:
        failures.append("credential persistence contract failed")
    if execution.get("image_bytes_persisted") is not False:
        failures.append("image persistence contract failed")
    if execution.get("seedream_invoked") is not False:
        failures.append("Seedream was unexpectedly invoked")

    corpus = payload.get("corpus", {})
    for name in ("garment_images", "look_images", "reasoning_requests"):
        if corpus.get(name, 0) < 3:
            failures.append(f"insufficient {name}")
    if corpus.get("requests_per_model") != 9:
        failures.append("expected exactly nine requests per model")

    calls = payload.get("calls", {})
    for label in ("lite", "mini"):
        model_calls = calls.get(label, [])
        if len(model_calls) != 9:
            failures.append(f"{label} call count is not nine")
        for call in model_calls:
            serialized = json.dumps(call, ensure_ascii=False)
            if "data:image/" in serialized or "Authorization" in serialized:
                failures.append(f"{label} result persisted sensitive request material")

    summary = payload.get("summary", {})
    if set(summary) != {"lite", "mini"}:
        failures.append("both candidate summaries are required")
    decision = payload.get("decision", {})
    if "mini_meets_gate" not in decision:
        failures.append("missing Mini gate verdict")
    return not failures, failures


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_result.py RESULT_JSON COMPLETION_JSON")
    result_path = Path(sys.argv[1])
    completion_path = Path(sys.argv[2])
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    passed, failures = _validate(payload)
    completion = {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "summary": (
            "Live serial A/B artifact is complete and mechanically valid"
            if passed
            else "; ".join(failures)
        ),
        "output_artifact_path": str(result_path),
        "mini_meets_gate": payload.get("decision", {}).get("mini_meets_gate"),
    }
    completion_path.parent.mkdir(parents=True, exist_ok=True)
    completion_path.write_text(
        json.dumps(completion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(completion, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
