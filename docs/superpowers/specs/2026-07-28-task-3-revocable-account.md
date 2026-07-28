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
- The Product API remains OpenAPI-first. Generated `StyleCaptureAPI` DTOs stop at the iOS Core/API adapter; TCA reducers consume domain values and typed errors only.
- TCA `1.26.1` owns state, reducer composition, dependencies, effects/cancellation, navigation and restoration. `AuthenticationServices` and throwing Keychain operations are dependency clients; no ViewModel shell, global environment, DI container or custom router is allowed.

## Delivery slices and evidence

1. Apple identity boundary: malformed, oversized, unavailable, replayed and mismatched subject/audience/nonce cases; no secrets in exceptions/logs.
2. PostgreSQL boundary: migration upgrade/downgrade plus atomic concurrent binding, ownership reassignment, replay and tombstone integration tests on PostgreSQL.
3. Deletion boundary: repository, asynchronous job finalization and object-write regression tests proving freeze-before-delete behavior.
4. Contract boundary: regenerate OpenAPI and the Swift client, prove clean diff and compile, and keep generated DTOs outside reducers/domain.
5. Native boundary: SIWA request/nonce, Keychain save/restore/revoke, TCA onboarding/account reducers, TestStore success/failure/recovery/deletion, XcodeGen generation and hosted macOS compile/tests.
6. Milestone gate: dependency/license/privacy-manifest audit, fresh backend/iOS verification, and a booted iPhone Simulator walkthrough of the affected user flow. Persist initial, interaction, processing, success, failure and recovery screenshots plus an interaction recording; SwiftUI previews, hosted XCTest and DOM assertions do not substitute for this evidence. Run the structured visual verdict against the approved Journey/new-main references until it scores at least 90, then obtain six independent `APPROVE + CLEAR` reviews.

## Current checkpoint — 2026-07-28

- GREEN: 37 focused account tests on a fresh single-service PostgreSQL container, including concurrent binding/replay, same-identity convergence, tombstone write leases and migration `20260726_0016 -> 20260727_0017` downgrade/upgrade; Ruff clean and mypy clean across 97 affected source files.
- GREEN: fixed Apple token/JWKS endpoints, ES256 client-secret signing, bounded token/JWKS responses, forced JWKS rotation refresh, cross-check of exchanged subject/audience/nonce, typed failure mapping and no raw response/secret propagation.
- GREEN: transaction-scoped PostgreSQL advisory locks serialize anonymous subject, authorization-code and Apple-identity binding; concurrent different identities yield one typed conflict, concurrent replay yields one typed replay without moving the losing owner, and concurrent same-identity bindings converge on one account.
- GREEN: a shared subject-write lease now guards capture/job, wardrobe, Look/preference, render, pixel-trial, item-presentation, outfit-trace/purchase and derived-object writes. Upload acceptance holds the same lease through token claim and persistence, and canonical-subject resolution preserves pre-sign-in upload ownership after Apple binding. Deletion regressions cover late repository work, all three media processors, CaptureProcessor, derived object writes and prepared uploads; a focused 58-test cross-feature run plus targeted boundary suites pass without starting PostgreSQL.
- GREEN: account routes are present in both regenerated OpenAPI inputs, the generated-client freshness check passes, and 73 database-independent account/capture/render/pixel/item/OpenAPI tests plus the focused stable-upload-error tests pass.
- GREEN: hosted run `30346683867` at `a4f3b8f` passed product job `90234444390` and iPhone 17 simulator job `90234444498`, including the first TCA `AuthFeature` restore/sign-in/refresh/delete/recovery tests. This proves the reducer slice compiles and runs; live SIWA/Product API composition remains open.
- GREEN: a behavior-first generator regression proves the canonical H5 OpenAPI keeps FastAPI 3.1 nullable unions while the deterministic Swift projection removes only exact `T | null` pairs. Generated Swift now retains optional business fields such as `deviceName`. OpenAPI requires ordinary `Authorization` header parameters to be ignored, so Bearer injection remains a separate official OpenAPI Runtime `ClientMiddleware` boundary and is not claimed as generated DTO evidence.
- OPEN: compile the projected generated Swift client, complete live AuthenticationServices/Product API/throwing-Keychain composition, run the final hosted proof, then launch the built app in a booted local iPhone Simulator and operate the authentication/deletion failure-and-recovery flow. Capture and surface screenshots plus an interaction recording, clear visual score 90, and pass the final six-review gate.
- Resource rule: keep local verification single-process. Simulator evidence is required and may run as one simulator plus one serial build/test lane after a thermal/memory check; do not run Xcode, Docker and parallel media suites together.
