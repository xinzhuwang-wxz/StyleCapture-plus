# StyleCapture Journey Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan one milestone at a time. Use `superpowers:test-driven-development` for each behavior and `superpowers:verification-before-completion` before every completion claim.

**Goal:** Ship a China-first native iPhone app that converts one upcoming 3–7 day trip plus at least 8 slot-covering owned garments (12–30 recommended) into a purchased, executable outfit and packing plan, and prove production paid/verified use before scaling.

**Architecture:** Add a SwiftUI iOS 17+ client over the existing FastAPI modular monolith. Keep Item/Look/Outfit/Render as existing truths; add revocable accounts, Trip/Occasion/Packing orchestration, StoreKit entitlement ledger, deletion state machine and minimal product events. Generate the Swift API client from FastAPI OpenAPI, keep an offline GRDB projection/outbox, and route intelligent work through existing LiteLLM capability ports.

**Tech Stack:** SwiftUI, Observation, Swift Concurrency, NavigationStack, PhotosPicker, StoreKit 2, BackgroundTasks, OSLog, MetricKit, Swift Testing, XCTest/XCUITest, XcodeGen, GRDB.swift, Apple Swift OpenAPI Generator, Nuke, FastAPI, SQLAlchemy/Alembic, PostgreSQL/pgvector, Redis/Celery, COS/S3, LiteLLM Proxy, Promptfoo, OpenTelemetry, in-region control-gated Langfuse, Apple App Store Server Python library, Xcode Cloud/TestFlight.

---

## Execution rules

- Do not start Task 2 until Task 1's M0 paid-problem gate passes after the seven-day recruiting/offer window and at least 15 plan recipients reach `trip_end+7d`; record the actual maturity cutoff. A failed gate produces a documented pivot/stop, not speculative implementation.
- Before every task, update the matching milestone section in `docs/exec-plans/0043-stylecapture-journey-commercial-app.md` and copy in the exact reuse audit.
- Start with one failing public-behavior test, add the minimum implementation, then continue behavior by behavior.
- After a public API change, regenerate OpenAPI and compile the generated Swift client before continuing.
- Every user-visible task requires real iPhone simulator/device operation and screenshots for initial, interaction, processing, success, failure and recovery states.
- Every task ends with independent spec, architecture, reuse/license, security/privacy and conversion/UX review. Fix P0/P1 in the same task.

## Task 1: Validate the paid problem before product build

**Files:**

- Create: `docs/research/journey-validation/README.md`
- Create: `docs/research/journey-validation/interview-script.md`
- Create: `docs/research/journey-validation/concierge-plan-template.md`
- Create: `docs/research/journey-validation/decision-log.md`
- Create: `docs/research/journey-validation/metrics.schema.json`
- Create: `docs/research/journey-validation/.gitignore`
- Modify: `docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md`
- Modify: `docs/exec-plans/0043-stylecapture-journey-commercial-app.md`

**Behavior to prove:** A qualifying user with a real 3–7 day trip can understand the deliverable, receive a complete plan from her own clothes, accept or reject one ¥12 offer without pixel-world priming, and later report whether she actually executed it.

**Steps:**

1. Write a neutral interview script that captures a real trip within 30 days, current workaround, cost of failure, evidence of action, wardrobe-import tolerance and acceptance/rejection of one ¥12 offer. Reject leading “would you use AI?” questions and do not mix single-day occasions into the cohort.
2. Define a de-identified metrics schema; keep raw contact details and photos outside Git. The committed `.gitignore` must reject `participants/`, raw photos, recordings and exports.
3. Produce at least 15 complete concierge plans with a repeatable template: confirmed constraints, selected garments, day/activity looks, alternatives, deduplicated packing, gaps, user corrections and post-trip outcome. Offer every recipient the same ¥12 result and record at least five real, refundable payments or deposits; willingness, oral promises and “equivalent commitments” are not `real_paid`. Keep this research collection outside any App binary and never use it as an external payment link from iOS.
4. Calculate the M0 thresholds exactly as defined in the PRD/research audit. Pain and payment denominators are the qualified cohort/at-least-15 complete-plan recipients as specified; post-trip execution uses those same at-least-15 recipients, requires at least one planned main/alternative Look or traceable hard-constraint-preserving replacement, and counts non-response as not executed. Record exclusions and denominator for each percentage.
5. Write a `GO`, `PIVOT`, or `STOP` decision with objections and the next falsifiable hypothesis. Only `GO` enables Task 2.

**Verification:** JSON Schema validates every de-identified record; secret/PII pattern scan is clean; an independent product reviewer can recompute all ratios from the committed aggregate; no participant photo/contact/raw transcript is tracked.

## Task 2: Scaffold the native iOS foundation and contract generation

**Files:**

- Create: `apps/ios/StyleCaptureJourney/project.yml`
- Create: `apps/ios/StyleCaptureJourney/Config/Package.resolved`
- Create: `apps/ios/StyleCaptureJourney/.gitignore`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/App/StyleCaptureJourneyApp.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/App/AppEnvironment.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/App/AppRouter.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/DesignSystem/DesignTokens.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Database/AppDatabase.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Database/OutboxRecord.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/API/APIClient.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Observability/AppLogger.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/PrivacyInfo.xcprivacy`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/Localizable.xcstrings`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/AppDatabaseTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/LaunchTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StoreKit/StyleCaptureJourney.storekit`
- Create: `apps/ios/StyleCaptureJourney/OpenAPI/openapi.json`
- Create: `apps/ios/StyleCaptureJourney/OpenAPI/openapi-generator-config.yaml`
- Create: `apps/ios/StyleCaptureJourney/ci_scripts/ci_post_clone.sh`
- Create: `scripts/generate_ios_openapi_client.sh`
- Create: `scripts/bootstrap_ios.sh`
- Modify: `scripts/export_openapi.py`
- Modify: `.github/workflows/product-ci.yml`
- Modify: `scripts/check_boundaries.py`

**Behavior to prove:** The app launches, navigates through an empty Journey shell, migrates a local DB, restores navigation after relaunch, and compiles against a client generated from the current `/v1` OpenAPI schema.

**Steps:**

1. Add a failing Swift test for first-run database migration and outbox round trip.
2. Make `bootstrap_ios.sh --check` fail fast unless Xcode 26.x, Swift 6.2+ and XcodeGen 2.46.0 match, and print an exact Homebrew install/upgrade command plus detected/required versions. Define targets/configurations/shared schemes/packages in `project.yml`, generate `.xcodeproj` locally/CI and ignore it. Use exact SwiftPM version/revision requirements, forbid branch/range dependencies in CI, keep `Config/Package.resolved` under version control, copy it to the generated workspace's canonical SwiftPM path and byte-check it after resolution.
3. Implement the smallest App/Router/Environment composition using Apple Observation and explicit initializer injection; do not add a DI container or reducer framework.
4. Implement `AppDatabase` migrations and outbox storage through GRDB.
5. Extend existing `scripts/export_openapi.py` with repeatable `--output` and `--check` arguments, preserving deterministic sorted JSON without adding a YAML dependency. Export the same schema bytes to existing `apps/h5/openapi.json` and `apps/ios/StyleCaptureJourney/OpenAPI/openapi.json`; define `openapi-generator-config.yaml`, `StyleCaptureAPI` module and DerivedSources output; generate and compile during the build without committing generated source.
6. Add privacy manifest, localized permissions and OSLog redaction tests before any SDK is allowed.
7. Keep existing Python/H5/Compose job on Ubuntu. Add a separate pinned macOS/Xcode `ios` job for bootstrap, generate, test and privacy-manifest inspection; add Xcode Cloud `ci_post_clone.sh` to validate/install XcodeGen, generate the project and fail if the expected project/scheme is absent before archive. Record a clean-checkout Xcode Cloud discovery/archive result; if an uncommitted generated project cannot be selected, use the documented GitHub macOS signed-archive fallback or commit only a minimal reviewed workspace/shared scheme.
8. Register only the technical-design allowlist (`com.stylecapture.journey.outbox-refresh`, `...upload-resume`, `...image-preprocess`) in both `BGTaskSchedulerPermittedIdentifiers` and scheduling code, add `processing` mode only for the two `BGProcessingTask` entries, and prove permitted, expiration, denied, app-termination and relaunch behavior instead of adding a custom background runner.
9. Add a lightweight Swift boundary check in CI that forbids feature UI importing infrastructure or generated transport DTOs directly and forbids cross-feature internal imports; domain/application code sees explicit local protocols/types.

**Verification commands:**

- `uv run python scripts/export_openapi.py --output apps/h5/openapi.json --output apps/ios/StyleCaptureJourney/OpenAPI/openapi.json --check`
- `bash scripts/bootstrap_ios.sh --check`
- `bash scripts/generate_ios_openapi_client.sh --check`
- `xcodebuild -project apps/ios/StyleCaptureJourney/StyleCaptureJourney.xcodeproj -scheme StyleCaptureJourney -destination 'platform=iOS Simulator,name=iPhone 16' test`
- `uv run python scripts/check_boundaries.py services/backend/src`
- `pnpm test`
- `uv run pytest -q`

## Task 3: Replace anonymous cookie assumptions with revocable native accounts

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/account/domain.py`
- Create: `services/backend/src/stylecapture_backend/features/account/ports.py`
- Create: `services/backend/src/stylecapture_backend/features/account/application.py`
- Create: `services/backend/src/stylecapture_backend/features/account/infrastructure/models.py`
- Create: `services/backend/src/stylecapture_backend/features/account/infrastructure/repository.py`
- Create: `services/backend/src/stylecapture_backend/features/account/infrastructure/apple_identity.py`
- Create: `services/backend/src/stylecapture_backend/features/account/infrastructure/deletion_repository.py`
- Create: `services/backend/src/stylecapture_backend/features/account/interfaces/http.py`
- Create: `services/backend/migrations/versions/20260727_0017_accounts_sessions.py`
- Create: `services/backend/tests/account/test_domain.py`
- Create: `services/backend/tests/account/test_application.py`
- Create: `services/backend/tests/account/test_apple_identity.py`
- Create: `services/backend/tests/account/test_http.py`
- Modify: `services/backend/pyproject.toml`
- Modify: `uv.lock`
- Modify: `services/backend/src/stylecapture_backend/platform/session.py`
- Modify: `services/backend/src/stylecapture_backend/main.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Auth/AuthSession.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Auth/KeychainTokenStore.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Onboarding/SignInView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/AuthSessionTests.swift`

**Behavior to prove:** An anonymous subject can bind once to a valid Apple `sub`, refresh through a rotating server session, reject nonce/audience/signature/replay failures, and immediately lose access after session or account revocation.

**Steps:**

1. Write failing API tests for invalid audience, nonce mismatch, replayed authorization code, refresh reuse, revoked session and cross-subject binding.
2. Re-audit and pin the mature JWT/JWK implementation (PyJWT `[crypto]` is the default candidate) rather than implementing JOSE; record exact release/commit/license and Apple JWKS behavior.
3. Model Account, ExternalIdentity, DeviceSession, SubjectTombstone and a minimal DeletionRequest without FastAPI/SQLAlchemy imports.
4. Adapt the existing subject ownership boundary to resolve both anonymous and account sessions while preserving current H5 compatibility until migration is deliberate.
5. Verify Apple identity tokens behind an `AppleIdentityVerifier` port; only the infrastructure adapter knows JWKS/protocol details.
6. Store access/session metadata server-side and hashed rotating refresh tokens; never log the identity token or raw refresh token.
7. Define the temporary H5-cookie-subject to Account-subject mapping and migration/revocation/deletion priority; owner checks resolve one canonical subject and never accept two independent truths.
8. Add AuthenticationServices SIWA credential-state/revocation and Keychain flows using `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`. Account binding must atomically migrate the anonymous subject or leave both unchanged; logout/deletion tests prove token/key removal. Repository writes, job start/finalize and object-store writes must reject tombstoned subjects from this task onward.

**Verification:** focused backend tests; migration upgrade/downgrade on PostgreSQL; generated client compile; iOS auth tests; replay/cross-account adversarial test; log scan for tokens.

## Task 4: Deliver protected garment import on iOS and production object storage

**Files:**

- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Wardrobe/GarmentImportView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Wardrobe/GarmentImportModel.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Wardrobe/ProtectedPhotoStore.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Wardrobe/GarmentCorrectionView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/ProtectedPhotoStoreTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/GarmentImportJourneyTests.swift`
- Create: `services/backend/src/stylecapture_backend/features/capture/infrastructure/s3_object_store.py`
- Create: `services/backend/tests/capture/test_s3_object_store.py`
- Modify: `services/backend/src/stylecapture_backend/features/capture/interfaces/http.py`
- Modify: `services/backend/src/stylecapture_backend/features/capture/application.py`
- Modify: `services/backend/src/stylecapture_backend/platform/config.py`
- Modify: `services/backend/pyproject.toml`
- Modify: `uv.lock`
- Modify: `docker-compose.yml`

**Behavior to prove:** A user selects only chosen photos, imports in batches, sees per-file progress, retries after interruption, corrects model fields, and removes both local and remote source data without importing the H5 `localStorage` design.

**Steps:**

1. Write failing iOS tests for protected-file write, backup exclusion, cache deletion, retry restoration and duplicate detection.
2. Reuse PhotosPicker/Transferable and existing upload-ticket/hash/ownership contracts through the generated client.
3. Implement image type handling, HEIC decode, downsampling and metadata stripping with CoreTransferable, UniformTypeIdentifiers and ImageIO; use protected staging without requesting full-library permission.
4. Re-audit and pin boto3 S3 client as the default mature COS-compatible implementation; if a real COS smoke fails required checksum/lifecycle/SSE/signing behavior, compare the Tencent COS official SDK and record the decision.
5. Add a private S3/COS adapter behind the existing object-store port. Test namespace, signed URL TTL, checksum, encryption headers, lifecycle tags and delete audit.
6. Preserve existing MIME magic/decode/pixel/size/one-time-token defenses and re-run cross-user tests.
7. Exercise permission denied, corrupt image, HEIC, weak network, background interruption, duplicate photo, quota and deletion recovery in the UI.

**Verification:** iOS unit/UI tests; backend capture/object-store suite; a real COS staging smoke; packet/log inspection; mobile screenshot/video evidence.

## Task 5: Add Trip, Occasion, weather snapshots and packing domain

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/trip_planning/domain.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/ports.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/application.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/infrastructure/models.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/infrastructure/repository.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/infrastructure/weather.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/infrastructure/itinerary_parser.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/infrastructure/tasks.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/interfaces/http.py`
- Create: `services/backend/src/stylecapture_backend/features/trip_planning/interfaces/worker.py`
- Create: `services/backend/src/stylecapture_backend/platform/outbox/domain.py`
- Create: `services/backend/src/stylecapture_backend/platform/outbox/repository.py`
- Create: `services/backend/src/stylecapture_backend/platform/outbox/dispatcher.py`
- Create: `services/backend/src/stylecapture_backend/platform/outbox/inbox.py`
- Create: `services/backend/migrations/versions/20260727_0018_trips_packing.py`
- Create: `services/backend/tests/trip_planning/test_domain.py`
- Create: `services/backend/tests/trip_planning/test_application.py`
- Create: `services/backend/tests/trip_planning/test_http.py`
- Create: `services/backend/tests/trip_planning/test_repository.py`
- Create: `services/backend/tests/trip_planning/test_tasks.py`
- Create: `services/backend/tests/trip_planning/test_itinerary_parser.py`
- Create: `services/backend/tests/platform/test_outbox.py`
- Create: `services/backend/tests/platform/test_inbox.py`
- Modify: `services/backend/migrations/env.py`
- Modify: `services/backend/src/stylecapture_backend/main.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/ItineraryImportView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/ItineraryOCRService.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/ItineraryConfirmationView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/ItineraryOCRTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/ItineraryConfirmationTests.swift`

**Behavior to prove:** A valid Journey persists confirmed occasions, selected owned items, weather provenance and packing constraints; invalid dates/ownership/limits fail; duplicate retries are idempotent; a locked plan cannot be silently changed.

**Steps:**

1. First add an architecture/migration test proving every SQLAlchemy model, including PixelTrial and ItemPresentation, is present in Alembic metadata.
2. Write pure domain tests for date/timezone, occasion order, luggage limits, ownership references, packing deduplication, revision and lock invariants.
3. Implement pure entities/value objects and typed ports.
4. Add repository/models and reversible migration; test upgrade from the oldest supported schema and downgrade of the new revision.
5. Add weather adapter with source/captured/valid-until/confidence fields and explicit stale/unavailable states.
6. Use Apple Vision `VNRecognizeTextRequest` for on-device itinerary screenshot OCR. Do not upload or persist the raw screenshot by default. Parse extracted text through a typed application port only after explicit user action; show every Occasion field for manual confirmation before persistence. Tests prove unconfirmed output is not truth and raw image/text never enters logs/events.
7. Re-audit WeatherKit client/REST coverage, attribution, quota, China target-city quality and signed-server access against at least ten representative destinations; adopt it if the smoke passes, otherwise document the mature provider comparison before implementation.
8. Add transactional `outbox_messages`/`inbox_messages`, lease/`SKIP LOCKED` dispatcher, payload hash conflict, bounded retry and dead-letter behavior. Trip, weather, commerce, deletion and costly AI jobs must use it.
9. Add owner-enforced, versioned, idempotent `/v1/trips` and packing endpoints. Scope idempotency by subject/method/canonical path/payload hash; same-key different payload returns `409`, stale version returns `412`.
10. Audit the commercial Journey path's existing capture/render/costly-AI dispatches: migrate every transaction-coupled dispatch to the PostgreSQL outbox, or document a bounded exception with a compensating idempotency/recovery test. Direct Celery `send_task` success is never delivery evidence.
11. Minimize encrypted outbox payloads and define per-environment KMS/secret-manager keys, rotation with old-key replay support, least-privilege dead-letter decryption and audited operator access.

**Verification:** domain/property tests; PostgreSQL repository and migration tests; OpenAPI diff/client compile; boundary checker; cross-owner and stale-version tests.

## Task 6: Orchestrate executable plans without duplicating the outfit engine

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/trip_planning/planning.py`
- Create: `services/backend/tests/trip_planning/test_planning.py`
- Create: `services/backend/tests/trip_planning/test_planning_worker.py`
- Create: `services/backend/tests/trip_planning/test_commercial_capability_journey.py`
- Modify: `services/backend/src/stylecapture_backend/features/trip_planning/application.py`
- Modify: `services/backend/src/stylecapture_backend/features/trip_planning/interfaces/http.py`
- Modify: `services/backend/src/stylecapture_backend/features/trip_planning/interfaces/worker.py`
- Modify: `services/backend/src/stylecapture_backend/features/outfit/application.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/JourneyBuilderView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/PlanPreviewView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Journey/PlanRevisionView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Packing/PackingListView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/JourneySyncTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Network/NetworkMonitor.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Sync/OutboxSyncCoordinator.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/JourneyPlanningTests.swift`
- Modify: `scripts/check_boundaries.py`

**Behavior to prove:** The free Day 1 travel preview uses only selected owned items, satisfies hard constraints and explains tradeoffs without exposing paid alternative details; the paid plan has validated alternatives, Day 2–7 and a deduplicated packing list, supports single-slot replacement, and returns a truthful rule-ranked plan when LiteLLM fails.

**Steps:**

1. Add failing trace tests for no invented item, weather/formality/warmth/walking/must/exclude/luggage constraints, multi-day reuse, slot lock, local replacement and LLM failure.
2. Adapt the existing Outfit application through a typed port. Do not copy its ranking, provider payload or prompt into Trip or Swift.
3. Generate candidate plans deterministically, use LiteLLM only for closed-candidate rerank/explanation, validate output, and persist the accepted revision.
4. Reserve a budget before model work and release it on timeout/failure; return `202` jobs with idempotent status.
5. Build SwiftUI journey/preview/revision/packing surfaces on the generated client and GRDB outbox. Use `NWPathMonitor` only to schedule retries; request results remain authoritative.
6. Exercise stale weather, no suitable shoe, provider timeout, app termination and offline packing recovery.
7. Add API and UI negative entitlement tests: without a verified pack, only the Day 1 main Look and non-revealing locked summaries are readable; alternative details, Day 2–7, replacement, packing, gaps and weather revisions return stable `PAYWALL_REQUIRED` without leaking content.
8. Add one generated-contract commercial capability test for create → selection → 202 preview/poll → paywall denial → verified entitlement → paid plan → replace → lock → offline packing → completion, including retry, duplicate request, stale version, provider failure and deletion tombstone. Facade tests or fixed local servers cannot substitute.
9. Extend the architecture checker across `skills/`, future App Intents and agent adapters: forbid provider endpoint/model/key, prompt, DB/storage/queue client, StoreKit verification, copied planning rules and hand-maintained DTOs. Allowlist only the existing ADR-0006 standalone Doubao directory and report it as excluded from Journey runtime/evidence. Do not create a public Journey Skill in P0.

**Verification:** trip/outfit and commercial-capability suites; architecture scan; real hosted-provider smoke with trace ID; generated-client compile; iOS unit/UI/weak-network tests; plan-quality rubric; visual verdict ≥90.

## Task 7: Implement StoreKit products and server entitlement ledger

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/commerce/domain.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/ports.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/application.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/infrastructure/models.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/infrastructure/repository.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/infrastructure/apple_store.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/infrastructure/retained_transactions.py`
- Create: `services/backend/src/stylecapture_backend/features/commerce/interfaces/http.py`
- Create: `services/backend/migrations/versions/20260727_0019_commerce_ledger.py`
- Create: `services/backend/tests/commerce/test_domain.py`
- Create: `services/backend/tests/commerce/test_application.py`
- Create: `services/backend/tests/commerce/test_notifications.py`
- Create: `services/backend/tests/commerce/test_reconciliation.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Entitlements/EntitlementStore.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Paywall/JourneyPaywallView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Paywall/PurchaseController.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Paywall/RenewalReminderScheduler.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Paywall/SubscriptionManagementLinkView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/PurchaseControllerTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyTests/RenewalReminderSchedulerTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/PurchaseJourneyTests.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/SubscriptionManagementTests.swift`
- Modify: `apps/ios/StyleCaptureJourney/StoreKit/StyleCaptureJourney.storekit`
- Modify: `services/backend/pyproject.toml`
- Modify: `uv.lock`
- Modify: `services/backend/src/stylecapture_backend/main.py`

**Behavior to prove:** A contextual paywall unlocks one ¥12 travel pack from an Apple-verified transaction; duplicate notifications do not double grant; failure does not consume; restore, refund and revocation converge to the correct ledger. Subscription products can pass their technical lifecycle without becoming the default offer before the repeat gate.

**Steps:**

1. Write pure ledger tests for grant/revoke/reserve/consume/release and every notification order/replay permutation.
2. Implement StoreTransaction, EntitlementLedgerEntry, UsageReservation and isolated StatutoryTransactionRecord domain objects and transactional repository. Product queries cannot read the retained statutory record after account deletion.
3. Pin `app-store-server-library-python` in backend dependencies/lockfile; verify JWS certificate chain, environment, bundle/product IDs, signed data and `appAccountToken` with explicit fixtures. Do not trust a client boolean.
4. Add notification inbox/idempotency and scheduled history reconciliation.
5. Build StoreKit 2 product/load/purchase/restore/transaction-update flow; only `.verified` proceeds and finishing occurs after durable server receipt.
6. Compare StoreKit `ProductView` with the contextual pack-first journey for localization, accessibility and conversion. Reuse it when it can clearly show one-time ¥12 and the Day 2–7/alternatives/deduplicated-packing/gaps/weather unlock; otherwise keep the smallest custom SwiftUI wrapper. Configure `SubscriptionStoreView` and lifecycle tests separately, but do not show subscription as the default CTA until 60-day second-paid-Journey behavior reaches 25%; show annual only after a second paid Journey.
7. For every active auto-renewing subscription, schedule a visible in-app reminder at least five days before renewal with localized date, amount, period and the StoreKit subscription-management destination. Persist/recompute it across offline use and clock/time-zone changes; notification permission is optional and the in-app path remains available when denied. Account deletion copy links to subscription management and states that deletion does not cancel Apple billing.
8. Prove one verified pack unlocks exactly the purchased Journey, no other Journey; restore on another device reproduces the same entitlement, and refund/revocation returns paid endpoints to `PAYWALL_REQUIRED` while preserving the user's own garments and lawful transaction record.

**Verification:** StoreKit configuration tests; backend permutation/property tests; sandbox purchase/restore/refund/revoke/replay; TestFlight receipt; ledger/Apple reconciliation; accessibility and conversion review.

## Task 8: Add pixel completion, privacy-safe events and AI labels

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/product_events/domain.py`
- Create: `services/backend/src/stylecapture_backend/features/product_events/application.py`
- Create: `services/backend/src/stylecapture_backend/features/product_events/infrastructure/models.py`
- Create: `services/backend/src/stylecapture_backend/features/product_events/infrastructure/repository.py`
- Create: `services/backend/src/stylecapture_backend/features/product_events/interfaces/http.py`
- Create: `services/backend/migrations/versions/20260727_0020_product_events_pixel_state.py`
- Create: `services/backend/tests/product_events/test_event_schema.py`
- Create: `services/backend/tests/trip_planning/test_pixel_retention.py`
- Create: `services/backend/tests/render/test_ai_content_labels.py`
- Modify: `services/backend/src/stylecapture_backend/features/render/processing.py`
- Modify: `services/backend/src/stylecapture_backend/features/render/infrastructure/collage.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Observability/ProductEventClient.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/PixelJournal/PixelJournalView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/PixelJournal/MementoShareController.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Notifications/WornReminderScheduler.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/PixelCompletionTests.swift`

**Behavior to prove:** Real plan/packing/worn/completion events unlock a minimal local-first pixel artifact; the share card contains no precise trip/person data; AI-derived files retain visible and implicit labels after save/share; packing-proxy and confirmed-worn VSS can be recomputed independently from minimal events.

**Steps:**

1. Define an allowlisted event schema and add rejection tests for photo, exact location, itinerary text, free text, provider payload, token and unknown keys.
2. Persist first-party events with `journey_id`, subject pseudonym, fixed travel template, offer arm, product ID, localized price/currency, store environment, acquisition source, event time, eligibility reason, test-user flag, maturity, app/experiment version, entitlement, duration and enum error code.
3. Derive a minimal local-first pixel retention layer from verified domain events, adapting only approved existing art assets. Do not make cloud pixel archives or a complex progression system a prerequisite for production paid validation.
4. Add visible label composition and required metadata at the render/export boundary; test resize/share/save paths.
5. Build a privacy-safe share sheet and UserNotifications worn-confirmation loop. Request permission contextually, keep notification text free of exact trip/person data, and provide a complete denied-permission path.

**Verification:** event schema/property tests; file metadata inspection; screenshot crop/share/save tests; VSS query recomputation; App Privacy field mapping; visual verdict ≥90.

## Task 9: Implement whole-account deletion and release security controls

**Files:**

- Create: `services/backend/src/stylecapture_backend/features/account/deletion.py`
- Modify: `services/backend/src/stylecapture_backend/features/account/infrastructure/deletion_repository.py`
- Create: `services/backend/src/stylecapture_backend/features/account/infrastructure/deletion_tasks.py`
- Create: `services/backend/migrations/versions/20260727_0021_account_deletion.py`
- Create: `services/backend/tests/account/test_deletion.py`
- Create: `services/backend/tests/account/test_deletion_resurrection.py`
- Create: `services/backend/tests/security/test_cross_account_access.py`
- Create: `services/backend/tests/security/test_cost_abuse.py`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Features/Settings/AccountDeletionView.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Auth/AppAttestClient.swift`
- Create: `apps/ios/StyleCaptureJourney/StyleCaptureJourneyUITests/AccountDeletionTests.swift`
- Create: `docs/security/JOURNEY-DATA-FLOW.md`
- Create: `docs/security/JOURNEY-PROCESSOR-REGISTER.md`
- Create: `docs/security/JOURNEY-RELEASE-CHECKLIST.md`
- Modify: `services/backend/src/stylecapture_backend/main.py`
- Modify: `services/backend/src/stylecapture_backend/platform/config.py`
- Modify: `.github/workflows/product-ci.yml`

**Behavior to prove:** Deleting an account immediately blocks old credentials and eventually removes all product data without old workers resurrecting it; privacy claims match real traffic and release artifacts.

**Steps:**

1. Write a failing multi-system deletion test with a job paused before deletion and resumed after tombstone.
2. Implement deletion states, retryable steps, evidence timestamps, processor callbacks, statutory-record isolation and user-visible status.
3. Revoke Apple authorization, device sessions and pending work before deleting media/data; enforce subject tombstones at every write boundary.
4. Add App Attest/DeviceCheck verification, account/product/provider cost quotas and anomaly blocking.
5. Restrict production OpenAPI/docs; add secret scan, SBOM, dependency audit, SAST, archive privacy report and SDK signature/manifest checks.
6. Complete data-flow/processor/privacy/filing artifacts. Packet capture and provider-side sentinel tests must prove that before applicable consent no photo, itinerary/city/occasion, wardrobe description, free text, stable subject identifier, cookie/token or other personal information reaches any third-party AI processor, while the deterministic/local fallback remains functional. China P0 must have no overseas person-photo route.

**Verification:** deletion convergence and resurrection tests; SIWA/account revocation; cross-account suite; mobile/API penetration test; network capture; archive privacy report; App Privacy reconciliation; no P0/P1 security/privacy finding.

## Task 10: Deploy, observe, soft launch and enforce decision gates

**Files:**

- Create: `infra/production/README.md`
- Create: `infra/production/terraform/`
- Create: `infra/production/runbooks/deploy.md`
- Create: `infra/production/runbooks/rollback.md`
- Create: `infra/production/runbooks/restore.md`
- Create: `infra/production/runbooks/storekit-reconciliation.md`
- Create: `infra/production/runbooks/privacy-incident.md`
- Create: `services/backend/src/stylecapture_backend/platform/telemetry.py`
- Create: `services/backend/src/stylecapture_backend/platform/ai_observability.py`
- Create: `services/backend/src/stylecapture_backend/platform/observability_deletion_index.py`
- Create: `services/backend/tests/platform/test_telemetry_privacy.py`
- Create: `services/backend/tests/platform/test_ai_observability_privacy.py`
- Create: `services/backend/tests/platform/test_ai_observability_canary.py`
- Create: `services/backend/tests/platform/test_observability_retention.py`
- Create: `docs/security/JOURNEY-DATA-RETENTION-SCHEDULE.md`
- Create: `infra/production/langfuse/README.md`
- Create: `infra/production/langfuse/compose.yaml`
- Create: `infra/production/otel-collector/config.yaml`
- Create: `infra/production/otel-collector/privacy-allowlist.yaml`
- Create: `infra/production/runbooks/ai-telemetry-leak.md`
- Create: `evals/promptfoo/journey-smoke.yaml`
- Create: `evals/promptfoo/journey-quality.yaml`
- Create: `evals/promptfoo/journey-redteam.yaml`
- Modify: `docker-compose.yml`
- Modify: `deploy/Caddyfile`
- Modify: `.github/workflows/product-ci.yml`
- Modify: `services/backend/pyproject.toml`
- Modify: `uv.lock`
- Modify: `package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md`
- Modify: `docs/exec-plans/0043-stylecapture-journey-commercial-app.md`

**Behavior to prove:** A signed TestFlight/App Store build talks to a recoverable managed production stack, operators can see SLO/cost/queue/entitlement health without seeing sensitive content, and D30/D90 evidence automatically leads to scale/iterate/pivot/stop.

**Steps:**

1. Re-audit and pin Terraform, TencentCloud provider, OpenTelemetry SDK/instrumentation/exporter and Langfuse-compatible versions/licenses; update dependency lockfiles. Provision managed PostgreSQL, Redis, COS/private CDN, WAF/load balancer, secret manager and at least two stateless API replicas through reviewed infrastructure code.
2. Separate worker queues by capture/render/trip/import profile with explicit concurrency, timeout, retry, dead-letter and alert behavior.
3. Add OpenTelemetry/Prometheus metrics for API p95, DB pool/query, queue wait/depth, provider error/latency, Redis memory, model cost, entitlement drift and deletion SLA. Labels must be bounded and non-sensitive: allow only route template, capability, queue, provider alias, status class and enum error; forbid journey/subject/request/order/device IDs and every free-form value as labels.
4. Gate Langfuse by edition and controls before deployment: private network/TLS only; public signup, email-password auth and deployment telemetry disabled; SSO+MFA, least privilege, audit, isolated projects/keys, approved TTL/export/delete and pinned digest/SBOM/CVE evidence required. Use OSS only when external controls close every gap; otherwise use a licensed edition or block release. The retention schedule records each store's active TTL, backup TTL, legal basis, owner, deletion API/query and evidence retention; management audit retention/access review and API-key rotation have fixed periods and tests.
5. Connect AI observability only through an application metadata allowlist and an independent Collector allowlist/drop policy. Explicitly reject the default LiteLLM callback that captures prompt/completion. Sanitization fails closed; Langfuse/Collector availability may fail open for product traffic and must alert.
6. Add the pinned Promptfoo runner to `package.json`/`pnpm-lock.yaml` so it enters SBOM/audit; do not use online `npx --yes` in CI. Run three tiers (`smoke`, `quality-gate`, `redteam`) only on synthetic/authorized sanitized fixtures with one-time synthetic accounts and minimum-scope short-lived tokens. Set `PROMPTFOO_DISABLE_TELEMETRY=1`, `PROMPTFOO_DISABLE_SHARING=true`, `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true`, `PROMPTFOO_DISABLE_REMOTE_GENERATION=1`, `PROMPTFOO_DISABLE_TEMPLATE_ENV_VARS=1`, `PROMPTFOO_DISABLE_UPDATE=1`, `PROMPTFOO_CACHE_ENABLED=false`, and put config/cache/log under `$RUNNER_TEMP/promptfoo`; run `--no-cache --no-share --no-write --no-table` with output only to scanned JUnit. YAML also fixes `sharing: false` and cache/write/table false.
7. Maintain an encrypted, access-restricted subject-to-observability deletion index containing only opaque trace/dataset identifiers and expiry metadata; it exists only for deletion/evidence, uses per-environment rotating pseudonym keys, and deletes itself after convergence evidence expires. Delete and poll active databases, replicas, object versions, queues and datasets to verified absence. Immutable backups follow approved maximum-expiry or cryptographic-erasure SLA; quarantine restores replay subject tombstones before restored data becomes queryable, and must never claim immediate row deletion from a snapshot.
8. Inject privacy canaries and query FastAPI/Celery/LiteLLM structured logs, Langfuse stores/blob, Collector queues/local spool, Prometheus labels, DLQ/retry payloads, exception/crash systems, ingress/WAF logs, Promptfoo database/cache/stdout/stderr/output and CI artifacts, plus a provider mock/receiver packet capture, for zero sensitive hits. A positive-control allowed metadata event must arrive so disabling all telemetry cannot pass. Exercise sanitizer crash/exporter retry and prove the telemetry-leak incident runbook. Every OTel semantic-convention or Langfuse/LiteLLM upgrade runs a field-schema diff.
9. Prove migration, rolling deploy, rollback, backup restore to RPO ≤24h/RTO ≤4h, provider outage, Redis restart, Langfuse/Collector outage, notification replay and budget-degrade runbooks in staging.
10. Configure App Store Connect metadata, privacy, IAP and travel-only Custom Product Pages/Product Page Optimization; use Xcode Cloud/TestFlight for signed archives. Optimize against production paid VSS/CAC, never downloads alone.
11. Treat TestFlight as technical evidence only. Run production cohorts using the frozen metric dictionary: at least 200 eligible paywalls/20 payers for initial validation and 500/50 plus mature D90 outcomes for scale. Apply any-trigger kill rules, not a conjunctive kill rule.

**Verification:** clean-environment deploy; restore drill with RPO/RTO evidence; load test to the next threshold; chaos/provider failure recovery; TestFlight/App Review checklist; D30/D90 decision record; final independent APPROVE + CLEAR review.

## Completion claim

The Goal is complete only when Tasks 1–10 satisfy their observable outcomes with fresh evidence, the China-first release has no unresolved P0/P1, paid conversion and VSS pass the D90 gate, production restore/reconciliation are proven, and final product/spec, architecture, reuse/license, security/privacy, code-quality and conversion/UX reviewers all return clean verdicts. If the paid wedge fails its defined gates, a documented stop/pivot is a valid research outcome but is not permission to claim the original launch Goal complete.
