# Task 3 SDD brief — revocable account and private garment import

Status: active, incomplete

Parent: `docs/exec-plans/0043-stylecapture-journey-commercial-app.md` M2

Goal: `docs/engineering/STYLECAPTURE-JOURNEY-GOAL.md`

## Observable outcome

An existing anonymous user can sign in with Apple without losing owned records, receives revocable access and rotating refresh credentials, can resume safely after ordinary access expiry, and cannot read or write after account deletion. The native app stores credentials in Keychain and expresses authentication, restoration, failure, recovery and deletion through the exact-pinned TCA app shell. This milestone does not depend on optional M0 research or production commercial denominators.

## Required contracts

- Apple authentication uses `AuthenticationServices`, a hashed nonce, a single-use authorization-code exchange against Apple's fixed token endpoint, fixed issuer/audience/RS256 verification, bounded async JWKS retrieval, and one canonical Apple subject.
- Anonymous-to-account binding, authorization-code replay recording and owner reassignment commit atomically in PostgreSQL. Concurrent replay, concurrent binding and a previously bound source produce typed failures without partial ownership moves.
- Access and refresh lifetimes remain distinct. Refresh rotation keeps an absolute family expiry, detects reuse and revokes the family.
- Account tombstones are checked at HTTP principal resolution and again before repository writes, job finalization and owner-scoped object writes. A late worker cannot resurrect deleted data.
- The deletion request performs no Apple network I/O. One database transaction freezes/tombstones the canonical subject, revokes local session families, records the idempotent request and makes all encrypted Apple grant generations claimable. A dedicated Celery maintenance worker leases and retries the revoke operation, accepts only Apple `200`, and wipes ciphertext only through a matching generation/attempt/lease-owner CAS.
- The Product API remains OpenAPI-first. Generated `StyleCaptureAPI` DTOs stop at the iOS Core/API adapter; TCA reducers consume domain values and typed errors only.
- TCA `1.26.1` owns state, reducer composition, dependencies, effects/cancellation, navigation and restoration. `AuthenticationServices` and throwing Keychain operations are dependency clients; no ViewModel shell, global environment, DI container or custom router is allowed.
- The iOS Keychain boundary persists a secret-free deletion intent and one stable idempotency key before submission. A retryable network failure may reuse the retained bearer/key; accepted or ambiguous processing fails closed into typed reconciliation/cleanup state and cannot restore the authenticated shell.

## Delivery slices and evidence

1. Apple identity boundary: malformed, oversized, unavailable, replayed and mismatched subject/audience/nonce cases; no secrets in exceptions/logs.
2. PostgreSQL boundary: migration upgrade/downgrade plus atomic concurrent binding, ownership reassignment, replay and tombstone integration tests on PostgreSQL.
3. Deletion boundary: repository, asynchronous job finalization and object-write regression tests proving freeze-before-delete behavior; durable Apple grant outbox/lease/retry/CAS/wipe tests; idempotent replay after session revocation; Keychain deletion-intent/restart/retry/cleanup tests.
4. Contract boundary: regenerate OpenAPI and the Swift client, prove clean diff and compile, and keep generated DTOs outside reducers/domain.
5. Native boundary: SIWA request/nonce, Keychain save/restore/revoke, TCA onboarding/account reducers, TestStore success/failure/recovery/deletion, XcodeGen generation and hosted macOS compile/tests.
6. Milestone gate: dependency/license/privacy-manifest audit, fresh backend/iOS verification, and a booted iPhone Simulator walkthrough of the affected user flow. Persist initial, interaction, processing, success, failure and recovery screenshots plus an interaction recording; SwiftUI previews, hosted XCTest and DOM assertions do not substitute for this evidence. Run the structured visual verdict against the approved Journey/new-main references until it scores at least 90, then obtain six independent `APPROVE + CLEAR` reviews.

## Current checkpoint — 2026-07-29

- GREEN, source and database-independent behavior: the backend now atomically accepts deletion, revokes the local session family and exposes encrypted Apple grant generations only to the maintenance outbox. Claiming uses `FOR UPDATE SKIP LOCKED`; completion/failure uses generation, attempt and lease-owner CAS; active grants are not claimable; stale leases recover; unreadable ciphertext fails durably; replacement requires a fresh access and refresh token; Apple revoke accepts exactly `200` and streams without buffering the response body.
- GREEN, iOS source behavior: the Keychain token item is separate from a secret-free deletion-intent marker. The same idempotency key survives retry/restart; tokens remain only while a request can still be retried, then are removed after the server accepts processing. Restore, ambiguous responses and post-accept cleanup failures use typed reconciliation/cleanup states, never a generic sign-in or authenticated shell. `CancellationError` crosses every boundary unchanged.
- GREEN, generated contract: `ProductAuthAPI` calls the generated delete operation and supplies its generated `Idempotency-Key` header while the existing OpenAPI Runtime middleware supplies Bearer authorization. Canonical H5 and Swift-projected OpenAPI outputs were regenerated from one FastAPI source, H5 types were regenerated, export freshness passes, and the generated DTO boundary remains restricted to Core/API plus tests.
- GREEN, deployment surface: `worker-account` and `beat-account` use the existing Celery stack on the dedicated maintenance queue; base and production Compose overlays resolve with the intended commands, configuration and restart behavior. No second scheduler or worker framework was added.
- GREEN, fresh lightweight verification: 65 database-independent targeted backend tests passed; 21 PostgreSQL tests collect successfully; Ruff passed and mypy passed across 21 source files; all changed Swift files parse; iOS bootstrap/package graph/privacy/OpenAPI checks passed; H5 typecheck and both Compose config checks passed; `git diff --check` passed. Independent backend-outbox, iOS credential/security, ProductAuth/OpenAPI, architecture and deployment reviews are CLEAN. Evidence: `docs/evidence/journey/task-3/local-green-checkpoint.md`.
- OPEN: execute the 21 SQL tests and migration round trip on hosted PostgreSQL; compile and run the current Swift surface in hosted Xcode; then operate one booted local iPhone Simulator through initial, SIWA, retryable failure, accepted processing, reconciliation and cleanup recovery states. Replace the stale untracked Simulator artifacts with fresh matching screenshots/video, obtain visual score `>= 90`, and run the six milestone reviews against that frozen commit.
- Resource rule: local verification stays serial. Simulator evidence may use one simulator and `jobs=2` only after a thermal/memory check; never overlap Xcode, Docker and media workloads.
