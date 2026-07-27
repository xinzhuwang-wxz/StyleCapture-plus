# Optional external M0 research readiness status

Last audited: 2026-07-28 (Asia/Shanghai)

Status: `OPTIONAL_REAL_EXTERNAL_M0_RESEARCH_NOT_READY`

Scope: this checklist applies only if and when the team chooses to run real external M0 research operations such as Xiaohongshu/group recruitment, participant contact, personal-information intake, refundable-deposit collection, refunds, or raw evidence handling.

This file records optional external-research readiness evidence only. It does not authorize posting, participant contact, personal-information processing, deposit collection, refunds, or a product `GO` decision. Its missing items do not block Task 2–9 local app/backend/iOS implementation, Apple sandbox, staging, TestFlight technical verification, or mature-framework development.

## Ready

- Neutral Xiaohongshu, DM, approved-group and reminder copy exists in `recruitment-copy.md`.
- The draft participant notice, operator runbook, interview script, concierge template, de-identified schema and deterministic validator exist.
- Verified deposits/payments and successful post-trip execution require de-identified external `evidence_ref` values.
- The repository branch is clean, pushed, and contains no real participant aggregate or raw participant evidence.

## Missing external authority or evidence

| Requirement | Current evidence | Gate |
|---|---|---|
| Authorized legal subject name | No usable value found in tracked project documentation | Must be completed outside Git before any real notice or collection |
| Operator, privacy/deletion, complaint and merchant/refund contacts | `participant-notice.md` still contains explicit pre-launch placeholders | Must be completed by the authorized legal subject |
| Logged-in Xiaohongshu creator account | No existing Xiaohongshu creator tab was present; one direct read-only navigation attempt in each available browser surface did not establish a page or login-state signal | Do not publish or claim account readiness |
| Approved group-forward permissions | No approval evidence exists | Do not forward into groups |
| Authorized refundable-deposit merchant method | No tracked merchant/payment integration or authority evidence exists | Do not collect the ¥12 deposit |
| Isolated refund reserve and reconciliation owner | No evidence exists | Do not collect deposits |
| Approved external raw-data/evidence register | No access, retention, deletion or operator-control evidence exists | Do not receive proofs, garment photos, contacts or payment evidence |
| Real cohort, payments, refunds, plans and mature follow-up | No de-identified aggregate exists | Do not record M0 `GO`, `PIVOT` or `STOP`; do not use technical/sandbox/staging/TestFlight evidence as M0 market evidence |

## Audit notes

- The account check was read-only. No login, post, message, form submission, upload, payment or account change was attempted.
- Repository search found no tracked legal-subject/contact record suitable for the participant notice and no tracked merchant-payment configuration.
- A browser navigation failure is not evidence that an account does or does not exist; it is evidence that this session cannot safely establish account readiness.

## Next admissible external-research transition

External M0 execution may start only when the authorized legal subject supplies or makes available the missing account, contact, merchant/refund and controlled-data-store evidence. At action time, the operator must still follow the posting/payment confirmation and channel-permission gates in `operator-runbook.md`.

Task 2–9 local app/backend/iOS development, Apple sandbox, staging and TestFlight technical verification remain admissible while this optional external-research readiness status is not ready. No external research has run and no M0 decision exists.
