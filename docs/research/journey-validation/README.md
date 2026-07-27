# Journey M0 validation operating surface

This folder defines the repository-side controls for the M0 paid problem validation. It does not contain real participant contact details, raw photos, recordings, transcripts, payment screenshots, exports, or completion evidence.

## Execution package

- `recruitment-copy.md` contains copy-ready neutral recruiting text for Xiaohongshu, comments, DMs, approved group forwards, and seven-day reminders.
- `participant-notice.md` contains the participant-facing research notice template. All legal subject, contact, complaint, privacy, merchant, and refund placeholders must be completed by the authorized legal subject before real use.
- `operator-runbook.md` contains the external operating checklist for screening, proof deletion, pseudonymous IDs, merchant collection, refund reserve, delivery, follow-up, aggregate metrics, decision, incidents, and pause gates.
- `interview-script.md` contains the neutral screener, current-behavior interview, wardrobe tolerance questions, identical offer wording, and post-trip follow-up.
- `concierge-plan-template.md` contains the one-trip plan structure and identical ¥12 refundable deposit terms.
- `metrics.schema.json` defines the only commit-safe de-identified aggregate record shape.
- `decision-log.md` remains the decision record and must not record `GO`, `PIVOT`, or `STOP` without real de-identified evidence.

All actual posting, forwarding, participant contact, payment collection, refund handling, complaint handling, and legal/privacy disclosures require logged-in accounts, channel permission, merchant authority, and legal subject authorization outside these documents. This folder can prepare and constrain operations; it cannot claim those external actions are complete.

## Gate

Task 2 native iOS work remains blocked until the local M0 decision log records `GO` from real evidence:

- 20-30 qualified travelers, with a target of 30 recruits to preserve at least 15 mature plan recipients.
- Confirmed departure in 7-30 days.
- One real 3-7 day overnight trip. Single-day weddings, interviews, dates, and generic occasions are excluded.
- At least 8 owned garments available for the trip; 12-30 recommended for planning.
- At least 15 complete concierge plan recipients.
- One identical ¥12 refundable deposit offer, with identical rights and refund terms for every complete-plan recipient.
- Pain, real-paid, and execution denominators stay frozen as defined in `docs/product/STYLECAPTURE-JOURNEY-PRD.md`.
- Non-response and no-use stay in the execution denominator.
- Trip cancellations are refunded and recorded; they are not replaced with another scene.

## Recruiting controls

Use channel caps to keep the cohort from becoming one-channel or incentive-distorted:

| Source | Cap |
|---|---:|
| Natural search or public intent discovery | <=50% |
| Approved women/travel groups | <=35% |
| Second-degree referrals | <=25% |
| Professional creators | <=20% |

Do not use referral bounties, volume-paid group owners, information-feed ads, positive-feedback rewards, or completion cash rewards. Researchers may pay fixed labor fees only when the fee is independent of positive feedback, payment outcome, or execution outcome.

Exclude team members, direct family, duplicate subjects, pro trialists, non-ICP travelers, trips outside 7-30 days, non-3-7-day travel, and users unable to provide low-sensitivity proof.

Every de-identified aggregate record must include both `source_bucket` and `professional_creator` so these caps are recomputable. The validator enforces caps once the qualified cohort denominator reaches 20; smaller draft aggregates still report `channel_mix` but are not treated as final cohort cap evidence.

## Evidence handling

Permitted low-sensitivity proof:

- Redacted booking or itinerary proof with name, order number, ID, exact lodging, and contact data removed.
- Screenshot shown during qualification and deleted after qualification evidence is recorded.
- Garment photos needed for planning stay outside Git and outside App binaries.

Raw contact details, payment proof, refunds, photos, recordings, transcripts, and exports stay outside Git. The committed aggregate must use `metrics.schema.json` and pseudonymous `participant_id` values only.

## Validation command

When a real de-identified aggregate exists, validate and recompute it with:

```bash
uv run python scripts/journey_validation_metrics.py validate path/to/m0-aggregate.json
```

The command validates JSON Schema, scans for obvious contact details, enforces the one CNY 12 offer, rejects single-day cohorts, and recomputes:

- `pain_rate`
- `real_paid_rate`
- `execution_rate`
- `channel_mix`
- `maturity_cutoff`
- `all_m0_thresholds_passed`

The command is deterministic and uses the already locked Python `jsonschema` runtime.

## External actions not yet completed

The following require account or payment authority and must not be marked done until real evidence exists:

- Xiaohongshu post and reminder.
- Approved group forwards.
- Compliant merchant ¥12 item or deposit/refund permissions.
- Isolated refund balance.
- Privacy and deposit notice delivery.
- Real recruitment, payments, refunds, post-trip follow-up, and maturity cutoff.
