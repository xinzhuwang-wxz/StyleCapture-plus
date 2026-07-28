# Optional M0 research decision log

Status: `BLOCKED_FOR_REAL_EVIDENCE`

No `GO`, `PIVOT`, or `STOP` decision is recorded yet. Repository infrastructure is ready to collect, validate, and recompute M0 evidence, but recruitment, payments/deposits, plan delivery, refunds, and post-trip maturity have not happened in this repository.

The 2026-07-28 external-readiness audit found no established Xiaohongshu creator login signal, authorized legal-subject/contact values, group-forward approvals, merchant/refund authority, refund reserve, or controlled external evidence register. No posting, login, message, upload, payment or account mutation was attempted. See `external-readiness.md`.

## Decision options

### GO

Allowed only when all are true from real de-identified aggregate evidence:

- `pain_rate` denominator >=20 and rate >=60%.
- `real_paid_rate` denominator >=15, rate >=33%, and payer count >=5.
- `execution_rate` denominator >=15 and rate >=50%.
- Actual maturity cutoff is recorded from plan recipients who reached `trip_end+7d`.
- No raw contact details, photos, transcripts, recordings, payment proof, or exports are tracked.
- Objections and channel metrics are recorded separately.

### PIVOT

Use when the evidence is real but one or more thresholds fail and a sharper falsifiable wedge remains. The next hypothesis must name the cohort, offer, denominator, and kill condition.

### STOP

Use when the evidence is real and the travel wedge lacks enough paid or executed value to justify product build.

## Objections log

Record objections after real interviews:

| Date | Participant ID | Objection code | Severity | Notes |
|---|---|---|---|---|

## Next falsifiable hypothesis

Unset until real evidence exists. This optional research record does not block Tasks 2–10, Apple sandbox/staging/TestFlight, release readiness or aggregate Goal completion. If used later, only real mature evidence may support an M0 `GO`, `PIVOT` or `STOP`; technical evidence must not be counted as market evidence.
