# M0 operator runbook

This runbook controls the external M0 research execution package. It does not authorize publishing, collecting money, holding refunds, or processing personal information. Real operation requires a logged-in account, channel permission, merchant authority, refund funds, and the legal subject placeholders in `participant-notice.md` completed before launch.

## Operating principles

- Run one narrow study: 18+ participants with a real 3-7 day overnight trip departing in 7-30 days.
- Use one identical ¥12 refundable deposit offer for every complete-plan recipient.
- Keep the deposit separate from App, App Store, and future product unlock language.
- Do not promise outcomes, coach high pain scores, reward positive feedback, or treat oral willingness as payment.
- Keep raw contact, photos, itinerary proof, payment evidence, transcripts, and exports outside Git.
- Commit only de-identified aggregate metrics and Markdown operating documents.

## Launch readiness gate

Do not publish or collect deposits until all are true:

- Legal subject, operator, privacy/deletion, complaint, and merchant/refund placeholders are filled outside this repository by the authorized subject.
- Posting account is logged in and allowed to post in the selected channel.
- Group owner or admin has approved any group forward.
- Merchant collection method is approved for a refundable research deposit.
- A separate refund balance is available before accepting deposits.
- Operators know where raw materials stay outside Git and how to delete them.
- The frozen `metrics.schema.json` and `scripts/journey_validation_metrics.py` command are understood.

If any item is missing, pause external action and keep the decision log at `BLOCKED_FOR_REAL_EVIDENCE`.

## Recruitment and screening

1. Post or forward only approved neutral copy from `recruitment-copy.md`.
2. Track source caps while screening:
   - Natural search or public intent discovery: <=50%.
   - Approved women/travel groups: <=35%.
   - Second-degree referrals: <=25%.
   - Professional creators: <=20%.
3. Apply an intake throttle before accepting the next candidate from a source. If accepting that candidate would make the target cohort exceed a cap, stop that source and use another approved source.
4. Ask the screener in `interview-script.md`.
5. Reject and record exclusion if the candidate is under 18, duplicate, team/direct family, prior pro trialist, non-ICP, outside 7-30 days, not a 3-7 day overnight trip, single-day occasion, lacks proof, or lacks at least 8 owned garments.
6. Do not replace a cancellation with another scene under the same participant record.

## Proof and evidence handling

Permitted proof is a redacted screenshot or document shown for qualification only.

Operator flow:

1. Ask the participant to redact name, order number, ID, exact lodging, and contact details before showing proof.
2. View proof only long enough to confirm eligibility.
3. Record only de-identified eligibility status and an external `evidence_ref` if needed.
4. Delete proof only from local caches and files under operator control.
5. Never commit proof, screenshots, chat exports, transcripts, recordings, contacts, or payment evidence.

If proof cannot be controlled or deletion cannot be verified on a third-party channel, record the incident outside Git, pause that channel, and follow the notice and authorized legal subject process before resuming.

## Pseudonymous IDs

Assign one pseudonymous ID per participant before recording research data.

Format:

```text
m0-<source>-<short-random>
```

Examples:

```text
m0-xhs-7k2p9a
m0-wxg-3d8q1m
```

Keep the ID-to-contact mapping outside Git. Do not reuse IDs. Do not encode real names, handles, phone digits, city plus date combinations, payment identifiers, or trip details in the ID.

## Interview and planning

1. Record current behavior, pain score, cost of failure, evidence of action, and wardrobe tolerance before showing the offer.
2. Do not mention Feed, pixel world, try-on, App unlock, or AI novelty before offer recording.
3. Build one `concierge-plan-template.md` plan using only the participant's trip constraints and owned garments.
4. Use at least 8 selected garments for complete plans; 12-30 is recommended.
5. Include Day 2-7, alternatives, cross-day deduplicated packing, gaps, and weather revisions when the real trip requires those days.
6. Save raw garment photos and operational plan drafts outside Git.

## Offer and payment

Show exactly one offer to every qualified complete-plan recipient:

- ¥12 refundable deposit.
- Same rights and refund terms for every recipient.
- Research concierge result only.
- Not an App unlock, not an App Store product, not an external iOS payment link.

Record aggregate outcome as:

- `paid`
- `declined`
- `refunded`

`real_paid` requires `verified_payment` or `verified_deposit` plus `offer.evidence_ref` in the de-identified aggregate. Willingness, "I would pay", oral promise, creator barter, group owner access, or equivalent commitment is not `real_paid`.

## Merchant collection and refund reserve

- Use only a merchant collection method authorized by the legal subject.
- Keep a refund balance isolated from operating spend before taking deposits.
- Reconcile deposits and refunds outside Git.
- Store payment screenshots, merchant exports, account identifiers, and refund proof outside Git.
- Use `evidence_ref` values in aggregate metrics; do not commit payment artifacts.

Pause payment collection if merchant access changes, refund balance is insufficient, a refund fails, or payment proof cannot be segregated from Git/issue/PR surfaces.

## Delivery

1. Deliver the complete plan through the approved participant channel.
2. Record `complete_plan_delivered=true` only after the participant receives the complete plan and the identical offer is shown.
3. Record user corrections without preserving identifying raw text in Git.
4. If the operator cannot deliver the listed research result, refund the deposit and record `refunded`.

## Cancellation and refunds

Refund triggers:

- Operator cannot deliver the plan.
- Participant cancels the trip.
- Duplicate or erroneous collection.
- Legal subject requires refund for complaint, withdrawal, or operational incident.

Trip cancellations are refunded and recorded; they are not replaced with a new scene in the same record.

## Post-trip follow-up

Run follow-up only after `trip_end+7d`.

Ask whether the participant used:

- At least one planned main Look.
- At least one planned alternative Look.
- A replacement that preserved the original hard constraints.

Record execution outcome using schema values:

- `planned_main_or_alternative`
- `hard_constraint_preserving_replacement`
- `not_executed`
- `non_response`
- `not_mature`

Non-response, unclear use, and explicit no-use do not count as execution successes.

## Metrics aggregate

When real de-identified records exist, create an aggregate matching `metrics.schema.json` outside raw-data folders. Use the schema `required` arrays as the only authoritative field checklist; do not treat this runbook as a schema copy.

De-identified shape:

- One cohort object with `schema_version`, `cohort_id`, `frozen_at`, and `records`.
- Each `records[]` entry uses one pseudonymous `participant_id` and every field required by `metrics.schema.json`.
- No extra fields outside the schema.
- `offer.evidence_ref` is required when payment evidence is `verified_payment` or `verified_deposit`.
- `post_trip.evidence_ref` is required for successful execution outcomes.

Use `evidence_ref` only as a pointer to an external controlled evidence register. It must not reveal contacts, payment handles, exact lodging, account IDs, or raw file names containing personal data.

Validate with:

```bash
uv run python scripts/journey_validation_metrics.py validate path/to/m0-aggregate.json
```

## Freeze, validate, and decide

1. Freeze the cohort after the seven-day recruiting/offer window and once at least 15 plan recipients have reached `trip_end+7d`.
2. Set `frozen_at` to the decision cutoff datetime.
3. Run the validator.
4. Copy only the recomputed aggregate metrics into the decision evidence summary.
5. Record `GO`, `PIVOT`, or `STOP` in `decision-log.md` only from real de-identified evidence.

`GO` requires all thresholds:

- `pain_rate`: denominator >=20 and >=60% at pain score 7/10 or higher.
- `real_paid_rate`: denominator >=15, >=33%, and payer count >=5.
- `execution_rate`: denominator >=15 and >=50%.
- Actual maturity cutoff recorded.
- No raw contact details, photos, transcripts, recordings, payment proof, or exports in Git.

## Incident and pause gates

Pause external operation immediately if any of the following occurs:

- Under-18 or non-ICP participant is accidentally admitted.
- A channel owner did not approve forwarding.
- Raw contact, photo, proof, transcript, payment, refund, or export data enters Git, issue, PR, screenshot evidence, app bundle, trace, log, or fixture.
- Payment is described as App unlock or App Store external payment.
- A participant asks to withdraw, delete, complain, or stop contact and the operator cannot complete the request.
- Refund balance is insufficient or refund fails.
- AI processor use would send personal data without the required disclosure and consent path.
- Source caps are exceeded in a final-size cohort.
- Operators discover a materially different offer, incentive, or promise was used.

Incident handling:

1. Stop the affected channel or payment flow.
2. Preserve a minimal incident note outside Git under the legal subject's controlled store.
3. Remove any prohibited committed material if present, following repository safety rules and without rewriting unrelated work unless explicitly authorized.
4. Do not resume until the legal subject approves the corrected process.
