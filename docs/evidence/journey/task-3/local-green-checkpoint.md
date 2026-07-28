# Task 3 Local GREEN Checkpoint — 2026-07-29

This is repository and database-independent development evidence for the durable account-deletion correction. It is not hosted PostgreSQL, signed iOS, TestFlight, production, revenue, market, or real-user evidence.

## Observable behavior now covered

- One backend transaction freezes/tombstones the canonical subject, revokes local session families, records the idempotent deletion acknowledgement and moves encrypted Apple grant generations into the durable maintenance outbox.
- The account maintenance worker claims only pending/failed generations with `FOR UPDATE SKIP LOCKED`, recovers stale leases, retries failures, accepts only Apple `200`, and wipes ciphertext only through generation/attempt/lease-owner compare-and-set.
- Replacement Apple grants require a fresh access and refresh token; an invalid replacement cannot corrupt or accidentally revoke the prior active grant.
- iOS persists a secret-free deletion intent and stable idempotency key before submission. Retryable failures reuse it; accepted or ambiguous processing and cleanup failures restore fail-closed into typed reconciliation/recovery UI, never the authenticated shell.
- The generated delete call carries the generated `Idempotency-Key` header and the official OpenAPI Runtime Bearer middleware. Generated transport DTOs remain inside Core/API and tests.
- The existing Celery/Redis deployment stack owns the dedicated `maintenance` queue and beat schedule; no new scheduler framework was introduced.

## Fresh local evidence

| Evidence | Result |
| --- | --- |
| Targeted database-independent backend suite | `65 passed in 1.38s` |
| PostgreSQL test discovery | `21 tests collected`: 7 repository tests and 14 SQL Apple-grant repository tests |
| Ruff | Passed on affected backend and tests |
| mypy | Passed on 21 affected files |
| Swift syntax | Every changed Swift file passed `swiftc -parse` |
| iOS bootstrap | `bash scripts/bootstrap_ios.sh --check` passed |
| SwiftPM graph | `python scripts/check_ios_package_graph.py` passed |
| Privacy manifest | `python scripts/check_ios_privacy_manifest.py` passed |
| Swift OpenAPI freshness | `bash scripts/generate_ios_openapi_client.sh --check` passed |
| Canonical/projected OpenAPI freshness | `scripts/export_openapi.py --check` passed |
| H5 generated types | TypeScript typecheck passed |
| Compose | base and production-overlay config resolution passed; no container started |
| Worktree whitespace | `git diff --check` passed |

The SQL tests were also pointed once at a deliberately unavailable dummy PostgreSQL port and failed only while establishing the migration connection. That probe is excluded from the pass count and is not a product regression. Execution of all 21 SQL tests plus migration up/down remains a hosted PostgreSQL gate.

## Independent read-only reviews

- Backend revocation outbox, races and cryptographic lifecycle: CLEAN, no P0/P1/P2.
- iOS Keychain/deletion intent, cancellation, retry and recovery: CLEAN, no P0/P1/P2.
- ProductAuth/generated OpenAPI authorization, idempotency and DTO boundary: CLEAN, no P0/P1/P2.
- TCA/app-shell, generated DTO, deletion-recovery and durable worker architecture: CLEAN after removing the unused bearer-shaped `deletion_status()` application/port path.
- Celery/Compose deployment surface: CLEAN; a beat health probe is optional non-blocking P2 operations polish.

## Open gates

- Hosted PostgreSQL test/migration execution.
- Hosted Xcode generated-client compile and current iPhone test suite.
- One fresh local Simulator walkthrough covering signed-out, SIWA interaction, retryable failure, accepted processing, reconciliation and local-cleanup recovery; stale untracked artifacts are excluded.
- Visual verdict `>= 90` and the frozen-commit milestone review set.
