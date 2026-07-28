# ExecPlan 0043: StyleCapture Journey Commercial App

> Living plan. Keep Progress, Surprises & Discoveries, Decision Log, and Outcomes current while the Goal is active.

- Branch: `codex/stylecapture-journey`
- Status: active delivery; Task 3 local GREEN pending hosted PostgreSQL/Xcode and fresh Simulator evidence
- Date: 2026-07-27
- Product: StyleCapture Journey（衣程）
- Target: China-first native iPhone app, iOS 17+

## Observable outcome

A user with an upcoming 3–7 day trip can select at least 8 slot-covering garments she already owns (12–30 recommended), receive an executable day/activity outfit plan with alternatives and a deduplicated packing list, unlock Day 2–7 through a ¥12 Apple in-app purchase, recover the purchase on another device, and later confirm what she actually wore. The app remains useful under weak connectivity, never invents owned garments, and turns completion into a private pixel journey memento.

The first release is successful when the China-first iOS product delivers this result end to end with verified purchase/recovery/refund/offline/deletion behavior, real-provider and Apple sandbox/TestFlight evidence, release controls, and no unresolved P0/P1. A polished Feed, a large digital wardrobe, photorealistic try-on, or a pixel world without verified scene success does not satisfy the outcome. Post-launch payment and execution metrics remain product signals, not an aggregate development-completion gate.

## Scope

### P0

- Native SwiftUI client with Journey creation, selective garment import, plan, packing, paywall, purchase restore, pixel journal, account and deletion.
- FastAPI `trip_planning`, `commerce`, revocable account/session, product event, deletion, and private object-storage capabilities.
- StoreKit 2 plus Apple server verification and Notifications V2.
- China-first privacy, data residency, AI-labeling, filing, 18+, security, and App Review evidence.
- Production-ready modular-monolith deployment with measurable scale triggers.

### Explicit non-goals

- Feed, infinite content, creators, following, chat, community, multiplayer pixel world.
- Generic AI stylist chat or full-wardrobe import before first value.
- Photorealistic virtual try-on in P0.
- Single-day wedding, interview, date or generic occasion templates; each requires its own future evidence and denominator.
- Android, iPad-specific UI, Apple Watch, web parity, or a second backend.
- Pre-launch microservices, Kubernetes, event streaming, a data warehouse, or a custom experimentation platform.

## Sources of truth

1. Active Codex Goal created from `docs/engineering/STYLECAPTURE-JOURNEY-GOAL.md`.
2. This living ExecPlan.
3. Current branch-local milestone ExecPlan and SDD task brief.
4. `docs/product/STYLECAPTURE-JOURNEY-PRD.md`.
5. `docs/architecture/STYLECAPTURE-JOURNEY-TECHNICAL-DESIGN.md`.
6. `docs/architecture/JOURNEY-SKILL-CAPABILITY-REGISTRY.md`.
7. `docs/adr/0007-native-ios-trip-planning-and-storekit.md` and applicable existing ADRs.
8. `docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md`.
9. `docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md` and local resource guardrails.

## Delivery strategy

The plan uses two commitments:

1. **Complete the native paid-product vertical slices.** Task 2–10 and M1–M7 proceed continuously through iOS/backend, generated contracts, Apple sandbox, staging, TestFlight and release evidence. No M0 recruitment, payment, maturity or production-scale metric may pause development or redefine completion.
2. **Preserve optional market-learning truthfulness.** Existing M0 research assets and production metrics may be used later, but only real attributable evidence can support those separate market claims. Technical/sandbox/TestFlight evidence never becomes fabricated revenue, WTP or user-execution evidence.

Create or update milestone ExecPlans and SDD task briefs only after the Goal starts so their acceptance criteria reflect the final reviewed plan. Execute them in the dependency order below without pausing between completed branch-local tasks. Do not read, create, edit, comment on, close, or otherwise touch GitHub Issues or PRs without explicit future authorization.

## Milestones and branch-local task order

### Optional research track — paid problem validation (not a milestone gate)

Outcome: a seven-day recruiting/offer window followed by post-trip maturity produces a reproducible go/pivot/stop decision from 20–30 qualified travelers, at least 15 complete plans, and one ¥12 offer. The decision waits until at least 15 plan recipients reach `trip_end+7d` and records the actual maturity cutoff.

Acceptance:

- `pain_rate` uses all qualified interviewees who completed the pain question, denominator ≥20, and must be ≥60% at 7/10 or higher.
- `execution_rate` uses every plan recipient whose trip has reached `trip_end+7d`, denominator ≥15, and must be ≥50% for a planned main/alternative Look or traceable hard-constraint-preserving replacement; non-response counts as not executed.
- `real_paid_rate` uses all qualified complete-plan recipients shown the one ¥12 offer, denominator ≥15, and must be ≥33% with at least five real refundable payments/deposits. It excludes willingness, oral promises and equivalent commitments. Research payment stays outside any App binary and never becomes an external iOS purchase link.
- The evidence set records recruiting source, upcoming date, completion, offer outcome (`paid|declined|refunded`), payment/deposit evidence status, objections, maturity and actual plan execution; it never treats a WTP choice as success.
- A future research outcome may inform pricing, positioning and iteration, but it does not block Task 2–10, M1–M7, TestFlight, release-readiness work or aggregate Goal completion.
- Missing legal-subject/contact, account/channel, merchant/refund or controlled-evidence-store inputs block only the optional external research operations that require them.

### M1 — iOS foundation and generated contract

Outcome: a signed debug app launches on small/main/large iPhones, persists an offline projection, authenticates through a fake public contract in tests, and compiles a client generated from the live FastAPI OpenAPI document.

Acceptance:

- TCA `1.26.1` app shell, SwiftUI/Observation rendering, design tokens, GRDB migrations/outbox, Nuke pipeline, OpenAPI generation, OSLog privacy, Swift Testing, TCA `TestStore` and XCUITest are wired.
- iOS module contract is TCA-native: features own reducer/state/action/view; pure domain rules are feature-local or `SharedDomain` only when needed; external adapters live in `Core/*`.
- XcodeGen produces the project deterministically from a reviewed spec; generated `.xcodeproj` is not a merge-conflict surface.
- `PrivacyInfo.xcprivacy`, localized usage descriptions, accessibility identifiers, StoreKit configuration, and Xcode Cloud workflow exist from the beginning.
- No API DTO, image cache, purchase verifier, DI container, custom Router, global Environment, ViewModel app shell, navigation framework, effect runner, scheduler-owning outbox coordinator, or sync database is reimplemented. Generated `StyleCaptureAPI` DTO imports are restricted to `Core/API` adapter code and its tests.

### M2 — Revocable account and private garment import

Outcome: a user can anonymously preview, bind with Sign in with Apple, import selected photos, correct recognition, resume failed uploads, and delete an item without cross-user access or sensitive local leakage.

Task 3 preflight and reuse decision (2026-07-28): preserve the current anonymous UUID as a compatibility input only, then atomically map it to one canonical account subject; do not replace ownership IDs piecemeal or allow cookie and account principals to remain independent truths. Continue the exact TCA `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978` pin because no reproducible public stable TCA 2.0 release exists yet and the current app already avoids the high-risk 1.x deprecated APIs. For Sign in with Apple, directly depend on PyJWT `[crypto]` `2.13.0` / `7144e4534c34810f4525dc4578a32addd8212cff` (MIT), reuse the already locked `cryptography 46.0.7` and `httpx 0.28.1`, keep Apple protocol/replay/binding/session policy behind `AppleIdentityVerifier`, and do not introduce or hand-write a second JOSE stack.

Acceptance:

- SIWA issuer/audience/nonce/signature/time and replay are verified server-side.
- Short access and rotating refresh sessions are revocable; refresh hashes, not tokens, are stored.
- Account milestone creates subject tombstones and the minimum deletion request immediately; every subsequent repository, job and object write rejects tombstoned subjects.
- Photos use protected private files and PhotosPicker; secrets use Keychain; sensitive files are excluded from backup.
- Capture retains its MIME/signature/decode/hash/owner/idempotency controls.
- Production object storage is private COS/S3 with per-subject namespaces, lifecycle, short signed URLs, SSE, and deletion audit.

### M3 — Journey, plan, packing, and offline recovery

Outcome: a user creates a 3–7 day trip with structured daily occasions, selects garments, receives one complete Day 1 main-Look preview plus non-revealing locked-value summaries, purchases the ¥12 pack, then replaces one slot, unlocks Day 2–7/all alternatives/deduplicated packing/gaps/weather revisions, locks the plan, and checks packing under weak/offline connectivity.

Acceptance:

- Trip/Occasion/Packing invariants and Alembic migrations are covered by domain/property/migration tests.
- Rule layer enforces weather, formality, warmth, walking, must/exclude, luggage, ownership, and no-hallucinated-item constraints.
- Existing Outfit application is orchestrated, not copied.
- Planning returns a truthful rule-ranked result if LLM explanation/rerank fails.
- Weather refresh creates a revision and never silently overwrites a locked plan.
- Outbox retry is idempotent and conflict behavior is visible.
- Without verified entitlement, alternative details, Day 2–7, replacement, packing, gaps and weather revisions return stable `PAYWALL_REQUIRED`; one verified pack unlocks exactly its purchased Journey and restore reproduces that entitlement.
- A full Product API capability test covers create → selection → 202 preview/poll → paywall denial → verified unlock → replace → lock → offline packing → completion. Existing Skills or facade-only tests cannot substitute for this evidence.

### M4 — StoreKit entitlement and contextual paywall

Outcome: after seeing Day 1, the user can buy a ¥12 Journey pack, recover it across devices, survive duplicate/refund/revocation notifications, and never lose or double-spend entitlement. Subscription may remain technically configurable but is not the P0 default CTA.

Acceptance:

- StoreKit 2 client accepts only verified transactions and uses stable `appAccountToken`.
- Server validates JWS with Apple's maintained Python library; the ledger is the entitlement truth.
- Purchase, restore, renewal, grace period, billing retry, refund, revocation, notification replay, and reconciliation pass sandbox/TestFlight tests.
- Failed AI or plan jobs release reservations and consume no paid unit.
- The pack paywall discloses its one-time price and exactly what unlocks: Day 2–7, all alternatives, cross-day deduplicated packing, gaps and weather revisions. A separately gated subscription surface discloses period, renewal, cancellation, privacy and terms.
- At least five days before renewal, the app shows an in-app renewal date/amount/period/cancel path regardless of notification permission; authorized notification is supplemental. Account deletion links to system subscription management and explains that deleting the account does not cancel the Apple subscription.

### M5 — Pixel completion and verified success

Outcome: plan lock, packing, post-trip worn confirmation, and Journey completion unlock minimal local-first pixel artifacts and a de-identified share card while producing separate packing-proxy and confirmed-worn VSS evidence.

Acceptance:

- Pixel state is derived from real milestones and is not the paid-result gate.
- Shared/exported artifacts omit face, exact date/location/hotel and source photos.
- AI-derived output preserves visible and metadata labels in preview, download, and share.
- Product event schema contains no free text, photo, itinerary source, precise location, provider payload, or IDFA.

### M6 — Account deletion, privacy, and security release gate

Outcome: the user can delete the whole account and revoke consent; old sessions and jobs cannot restore data; the release archive and production network behavior match published privacy claims.

Acceptance:

- Deletion state machine covers DB, object storage, derived media, embeddings, prompts, caches, jobs, external processors, active storage, and backup SLA.
- M6 adds a scoped deletion-receipt/capability status contract that exposes retryable stage progress without sensitive internal payloads; it must not require the bearer session revoked by the initial delete transaction. The unusable Task 3 bearer `GET /v1/account/deletion-status` route remains absent.
- Statutory transaction records are isolated and unavailable to product features.
- Packet capture and provider-side sentinels prove that before applicable consent no photo, itinerary/city/occasion, wardrobe description, free text, stable subject identifier, cookie/token, or other personal information reaches any third-party AI processor; the deterministic/local fallback remains functional.
- App Privacy, privacy manifest, Required Reason API, SDK signatures, DPA/processor register, privacy policy, terms, APP filing, AI filing/registration determination, and 18+ policy are complete.
- Account deletion uses the encrypted subject-to-observability deletion index and polls active databases, replicas, object versions, queues, traces, and dataset copies to verified absence. Immutable backups follow the approved maximum-expiry or cryptographic-erasure SLA; quarantine restores replay tombstones before data becomes queryable.
- The approved retention schedule and automated retention test cover every observability/eval store. Privacy canaries query application/Celery/LiteLLM/WAF and exception logs, DLQ/retry, Langfuse stores/blob, Collector queue/spool, Prometheus, Promptfoo stdout/stderr/database/cache/output, and CI artifacts. Sensitive markers have zero hits and an allowlisted metadata positive control arrives. Sanitizer-crash/exporter-retry and dependency field-schema-diff tests pass.
- Secrets scan, SBOM, dependency audit, SAST, cross-account/API auth tests, App Attest/DeviceCheck, rate/cost abuse tests, and mobile/API penetration tests have no P0/P1.

### M7 — Production deployment, conversion experiment, and D30/D90 gates

Outcome: TestFlight and China App Store soft launch run on managed infrastructure with rollback, reconciliation, observability, privacy-safe analytics, and conversion experiments.

Acceptance:

- API has at least two replicas; PostgreSQL, Redis, COS/CDN, WAF, queues, backup/restore, secrets, migrations, health, alerts, and rollback are exercised.
- App Store Custom Product Pages cover travel intent variants such as city/weather/luggage; Product Page Optimization optimizes acquisition against production paid VSS/CAC, not downloads. Wedding/date/interview pages wait for separate validated products.
- App Store release evidence is stored under `docs/evidence/app-store/task-10/` with checklists/artifacts for screenshots, app preview, review notes, demo account/credentials delivery process without secrets in Git, age rating, privacy nutrition/App Privacy, IAP review package, localization, and CPP/PPO.
- Langfuse is private-network/TLS-only with public signup/password auth/deployment telemetry disabled, SSO+MFA, least privilege, isolated keys/projects, approved retention/audit/delete controls and pinned image digest/SBOM/CVE gate; otherwise release is blocked.
- Promptfoo is lockfile/SBOM managed and runs in ephemeral isolated CI with the exact disabled telemetry, sharing, red-team remote, all remote generation, template-environment, update, cache, write, and table controls defined by implementation Task 10; only scanned JUnit output remains.
- TestFlight metrics are technical only and must not be reported as production behavior. Eligible-paywall, payer, VSS, repeat, refund and margin metrics are instrumented for post-launch decisions but are not Task 10 or aggregate Goal completion gates.
- Capacity changes follow the recorded p95/CPU/connection/queue/provider/budget/table-size triggers; no speculative service split.

## Reuse audit

Every milestone copies this table into its branch-local ExecPlan and adds exact inspected source commit/license before implementation.

| Capability | Candidates inspected | Decision | Constraint |
|---|---|---|---|
| App shell/state/effects/navigation/tests | TCA `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978`; versioned source tree <https://github.com/pointfreeco/swift-composable-architecture/tree/1.26.1>; sharing-state docs source <https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.1/Sources/ComposableArchitecture/Documentation.docc/Articles/SharingState.md> | Direct reuse | MIT; exact pin; pre-M2 audit completed 2026-07-28 and found no public stable 2.0 release or local high-risk deprecated API; Task 3 uses `@Shared(.fileStorage)` directly for the pure `Codable` navigation snapshot; revisit on a reproducible public 2.0 tag or new deprecation pressure |
| UI/rendering/concurrency | SwiftUI, Observation, Swift Concurrency | Direct reuse | iOS 17+; rendering/lifecycle only, not custom app shell |
| Xcode project | XcodeGen `2.46.0` / `8445e77` | Direct reuse | MIT; generated project, reviewable spec |
| Navigation restoration | TCA reducer state plus `@Shared(.fileStorage)` persisted `NavigationSnapshot` | Direct reuse | `NavigationSnapshotClient`, app-owned `UserDefaults` persistence, custom navigation persistence effect and status are removed; no `StackState` is introduced until the shell has a real navigation stack; reducer tests prove restore/deep-link behavior |
| Offline DB/outbox | GRDB.swift `v7.11.1` / `b83108d` | Direct reuse | MIT; explicit migrations and sync metadata |
| API contracts | FastAPI OpenAPI + Apple Swift OpenAPI Generator `1.13.0` / `af9a2a1` | Direct reuse | Apache-2.0; generated during build |
| Image pipeline | PhotosPicker/Transferable + Nuke `13.0.6` / `63a8fcb` | Direct reuse | No whole-library permission for selective import |
| Itinerary OCR | Apple Vision `VNRecognizeTextRequest` | Direct reuse | Device-side extraction; user confirms structured truth; raw screenshot stays local by default |
| Weather | Apple WeatherKit / WeatherKit REST | Candidate adapt | Gate on China city coverage, attribution, quota, server signing and degradation smoke; never invent forecasts |
| Purchase client/server | StoreKit 2 + Apple server Python `v3.1.2` / `4eaa224` | Direct reuse | Server ledger owns entitlement |
| Apple identity verification | AuthenticationServices + PyJWT `[crypto]` `2.13.0` / `7144e4534c34810f4525dc4578a32addd8212cff` + Apple fixed JWKS endpoint; existing `cryptography 46.0.7` and `httpx 0.28.1` | Direct/adapt reuse | Apple SDK + MIT/BSD-3-Clause; fixed issuer/audience/RS256 allowlist, explicit JWKS refresh/cache policy, nonce/code replay and canonical-subject policy remain behind the application port; never hand-write or add a second JOSE stack |
| COS object client | boto3 S3 client + COS compatible endpoint | Candidate adapt | Re-audit version/license and checksum/SSE/lifecycle/signing smoke; compare Tencent SDK only on measured incompatibility |
| Hosted purchase platform | RevenueCat SDK + official DPA | Rejected P0 | Duplicates backend entitlement ledger and adds US/AWS vendor/data surface for China-first; revisit after measured cross-platform/remote-paywall need plus in-region controls |
| Analytics | First-party events + App Store Connect | Direct reuse/adapt | No autocapture/session replay; Sensors Data needs commercial license |
| Wardrobe/outfit/render | Existing backend vertical modules | Direct/adapt reuse | New Trip references existing truths |
| Feed/community | Existing H5 | Rejected | Not the paid job; only pixel art assets may be adapted |
| Virtual try-on | FASHN/FastFit/current render seam | Rejected P0 | Overseas person-photo path and non-commercial license |
| AI gateway/budget | Existing LiteLLM Proxy | Direct reuse | One gateway and capability alias; no provider SDK in business code |
| AI jobs | Existing Celery/Redis + PostgreSQL outbox/inbox | Direct/adapt reuse | Idempotent bounded jobs; Temporal only after measured saga pain |
| Retrieval | Existing PostgreSQL/pgvector | Direct reuse | HNSW only after benchmark/scale trigger; no premature vector DB |
| AI eval/red team | Existing Promptfoo `0.121.19` | Adapt reuse | Product API target, versioned datasets, CI quality/security gates |
| AI observability | Langfuse + OpenTelemetry | Adopt before soft launch | In-region edition/control gate; metadata-only dual allowlist, verified retention/audit/RBAC/delete; no raw user content |
| Standard platform telemetry | OpenTelemetry SDK/instrumentation/exporter + Collector + Prometheus | Direct/adapt reuse | Pin compatible versions; bounded non-sensitive labels; no custom trace/export protocol |
| Production infrastructure | Terraform + TencentCloud provider | Direct reuse | Pin provider/version/license, reviewed plan and security gate; no ad-hoc cloud scripts |
| Generic agent framework | LangChain/LlamaIndex/PydanticAI | Rejected P0 | No open-ended tool/RAG need; duplicates domain/application/LiteLLM boundaries |
| Native shortcuts | Apple App Intents / App Shortcuts | Deferred direct reuse | Add only after paid core; calls same app service/generated client, no second planner |
| External agent surface | Generated OpenAPI + official MCP SDK candidate | Deferred | No public P0 Skill; requires mature delegated auth/consent/revocation/entitlement/deletion gate |
| Existing repo Skills | single-scene/collage thin clients; direct-provider Doubao standalone artifact | Legacy/support only | Cannot prove Journey; Doubao artifact excluded from China product runtime/evidence |

## Development loop and steering

### Event-driven checks

Run the milestone gate immediately when any of these occurs:

- public API/OpenAPI or persisted schema changes;
- a new dependency, provider, SDK, analytics field, permission, or data recipient is proposed;
- StoreKit, account/session, deletion, upload, entitlement, cost, or AI-label behavior changes;
- a visible user journey reaches its first working end-to-end state;
- tests are disabled/relaxed, a fallback is added, or duplicated/generated code appears;
- a milestone acceptance criterion first appears complete;
- a reviewer, TestFlight user, provider, or production trace exposes a new failure mode.

The gate checks Goal alignment, current acceptance criteria, reuse audit, data flow, duplication, architecture boundaries, product conversion, accessibility, performance, privacy, security, failure/recovery UX, and fresh evidence. Fix P0/P1 in the current milestone and rerun affected checks.

### Time-driven heartbeat

When active work lasts longer than one hour and the Codex automation surface is available, create one recurring hourly automation targeting this same task/worktree. It does not implement in a second branch. If automation is unavailable, run the same heartbeat prompt at every long-task checkpoint and event gate. It reads Goal, ExecPlan, current SDD task brief, diff, test output, review findings, traces and screenshots; stops duplicate work; corrects drift; updates decisions; and resumes the current milestone. It must not touch GitHub Issues or PRs without explicit future authorization. Disable it when the Goal completes, blocks, or the branch is intentionally paused.

### Per-milestone verification order

1. Domain/application tests and invariant/property tests.
2. Migration up/down, OpenAPI diff, generated client compile.
3. Integration with Postgres/Redis/Celery/COS and fake providers only through public ports.
4. Bounded real weather/model/Apple smoke where credentials and sandbox permit.
5. iOS unit, UI, StoreKit, permission, weak-network, offline, background, low-storage, Dynamic Type and VoiceOver runs.
6. Launch and operate the candidate build in one booted local iPhone Simulator after the hosted compile gate. Persist and surface real simulator screenshots/video for initial, input, processing, success, failure, recovery, paywall, purchase and deletion states; SwiftUI previews, hosted XCTest and DOM assertions are supporting evidence only. Compare visible states with the approved Journey/new-main references using the structured visual-verdict loop and require score `>= 90` before milestone completion.
7. Separate spec, reuse/license, architecture, code/security/privacy, and conversion/UX reviews.
8. Bounded changed-file cleanup, then rerun every affected check.

Each independent review persists a record using `docs/engineering/STYLECAPTURE-JOURNEY-REVIEW-TEMPLATE.md`; chat-only `APPROVE` is not evidence.

## Scale and operating model

- Keep one modular FastAPI deployment and one PostgreSQL truth through soft launch.
- Separate queues by work profile before separating services.
- Prefer managed PostgreSQL/Redis/COS, horizontal stateless API replicas, private CDN, WAF, explicit migrations, daily backups and practiced restores.
- Use a PostgreSQL transactional outbox/inbox for Trip, commerce, deletion, weather and costly AI messages; Celery delivery alone is never the transaction boundary.
- Use OpenTelemetry Collector + Prometheus for platform telemetry and an in-region control-gated Langfuse deployment for metadata-only AI traces/datasets/evals; do not build custom LLM dashboards or eval runners.
- Admit expensive model work only after entitlement and budget reservation; enforce per-user, per-product, per-provider, daily and global limits.
- Keep responsibilities singular: UsageReservation owns plan entitlements/uses; LiteLLM owns token/spend/provider accounting; RedisCostGuard owns only realtime concurrency/rate/abuse shedding.
- Alert at 80% model budget and degrade at 95% to deterministic planning/collage without representing it as model success.
- Scale API, DB, queue, Redis, provider and append-only storage only on the thresholds in the technical design.

## Progress

- [x] Sync original local `main` to `origin/main` and remove generated evidence drift.
- [x] Create `codex/stylecapture-journey` from current `origin/main` in an isolated worktree.
- [x] Establish fresh baseline: 239 JavaScript/Skill tests and 301 Python tests pass.
- [x] Audit existing product, domain, reuse boundaries, Apple stack, market, conversion and scale shape.
- [x] Narrow the first paid wedge to one 3–7 day travel job; defer single-day occasions to separately measured experiments.
- [x] Draft PRD, technical design, ADR, research/reuse audit and this ExecPlan.
- [x] Complete independent product, architecture, iOS, privacy/security and adversarial plan review; resolve all P0/P1.
- [x] Commit and push the reviewed planning baseline (`5bac2ff`).
- [x] Add the local M0 research operating surface: neutral interview script, concierge template, de-identified schema, raw-data Git exclusions, decision log, and deterministic recomputation validator.
- [x] Capture behavior-first RED/GREEN evidence for M0 schema/recompute validation.
- [x] Task 2 iOS foundation: source/config slice implemented with XcodeGen 2.46.0 bootstrap, TCA app/Journey shell, dependency clients, GRDB outbox, OpenAPI export inputs, privacy/localization/StoreKit manifests, CI wiring and boundary checks.
- [x] Hosted macOS Task 2 verification: GitHub Actions run `30317565521` at HEAD `055e11a5113a418898b2b308766dbe9d148cf9d9` passed both `product` job `90146355217` and `ios` job `90146355277`. The iOS job passed bootstrap, OpenAPI input checks, hosted simulator `xcodebuild test`, SwiftPM lock integrity, privacy manifest inspection and boundary checks. Evidence: `docs/evidence/journey/task-2/hosted-ci.md`.
- [x] Hosted Xcode trust gate: non-interactive CI uses `-skipPackagePluginValidation` and `-skipMacroValidation` only after exact Package.resolved seeding and post-build byte verification; final green hosted run `30317565521` proves this gate no longer blocks Task 2.
- [x] Task 2 review-fix round 1 RED: commit `2708778b74d9d499ec17dee3068a890462068204` added a failing navigation-persistence regression and executable iOS privacy-manifest validator before implementation. Hosted run `30318648806` confirmed the privacy validator failed against the old manifest. The first navigation RED was invalid as behavior evidence because `Result<Void, AppError>` blocked `Action: Equatable` synthesis before XCTest could execute; GREEN replaces it with a compile-safe explicit response enum.
- [x] Task 2 review-fix round 1 GREEN: hosted GitHub Actions run `30319519482` at HEAD `045974480dc82d53ddc546a97850b8c6859e5277` passed `product` job `90152256536` in 3m27s and `ios` job `90152256473` in 12m23s. Superseded run `30319082666` at HEAD `e738da598a2f740630b6a7da1a471cd47f0d4310` was intentionally cancelled by the agent after `product` passed because the old iOS step was monolithic and had been replaced by split dependency, package-graph, test, lock and privacy/boundary steps; its log records cancellation, not timeout, test failure, or Swift compile failure.
- [x] Pre-M2 TCA 2.0 audit: official release/migration evidence and the local API surface were re-checked on 2026-07-28. Keep the exact `1.26.1` pin for Task 3/P0 because 2.0 has no reproducible public stable tag and current code already avoids the high-risk deprecated APIs; reopen on a public 2.0 tag/beta package or new local deprecation pressure.
- [x] Task 3 reuse/security preflight: select PyJWT `[crypto]` `2.13.0` / `7144e4534c34810f4525dc4578a32addd8212cff` (MIT), reuse existing `cryptography 46.0.7` and `httpx 0.28.1`, fix Apple issuer/JWKS/algorithm inputs, and preserve one canonical subject through atomic anonymous-account binding.
- [x] Task 3 backend identity/account and deletion boundary tracer bullets: distinct absolute refresh expiry, access/refresh separation, typed replay/deletion/binding/session errors, hashed Apple nonce comparison, cross-subject rebinding rejection, fixed-endpoint authorization-code exchange, ES256 client-secret signing, bounded async token/JWKS retrieval, forced key-rotation refresh, exchanged subject/audience/nonce cross-check, shared repository/job/object-write tombstone leases and alias-aware upload ownership. Fresh evidence is 37/37 account tests on PostgreSQL, 73/73 database-independent cross-feature tests, focused stable-upload-error API tests, Ruff clean, mypy clean across 97 source files and generated-client freshness clean. This is partial backend/contract evidence only; compiled Swift Product API and iOS hosted proof remain open. The active SDD brief is `docs/superpowers/specs/2026-07-28-task-3-revocable-account.md`.
- [x] Task 3 native reducer checkpoint: hosted run `30346683867` at `a4f3b8f` passed product job `90234444390` and iPhone 17 simulator job `90234444498`, including AuthFeature restore/sign-in/refresh/delete/recovery TestStore coverage. Live AuthenticationServices and Product API adapters remain inside the current Task 3 slice.
- [x] Task 3 navigation restoration correction: current source removes the custom `NavigationSnapshotClient`, app-owned `UserDefaults` store, navigation persistence effect and navigation persistence status. `AppFeature.State` now initializes `@Shared var navigationSnapshot` with TCA's `.fileStorage(.styleCaptureNavigationSnapshot)` strategy; `NavigationSnapshot` is pure `Codable`, and the reducer owns restore/deep-link mutation. The app manifest no longer declares app-owned `CA92.1` because application Swift sources no longer directly use `UserDefaults`; swift-composable-architecture and swift-sharing required-reason APIs remain audited through their package manifests.
- [x] Task 3 durable deletion local GREEN checkpoint: one backend transaction freezes/tombstones the subject, revokes session families, records the idempotent deletion acknowledgement and makes encrypted Apple grant generations claimable by the dedicated Celery maintenance outbox. The worker uses short leases, retry/backoff and generation/attempt/lease-owner CAS, accepts only Apple `200`, and wipes ciphertext only after matching success. The iOS Keychain boundary persists a secret-free deletion intent plus stable idempotency key before submission, preserves credentials only while a retry can still authenticate, removes tokens after accepted processing, and restores into typed reconciliation/cleanup UI rather than the authenticated shell. Generated Product API calls carry both Bearer and `Idempotency-Key`; H5/iOS contracts are regenerated from the same FastAPI schema. Fresh lightweight evidence includes 65 targeted database-independent tests and mypy over 21 source files in `docs/evidence/journey/task-3/local-green-checkpoint.md`; hosted PostgreSQL/Xcode and fresh Simulator proof remain open.
- [x] Task 3 hosted candidate diagnosis: run `30393350600` at `db1d5a2` failed truthfully at the product Ruff format gate and at iOS linking of direct TCA `Sharing.FileStorageKey` symbols. The formatter-only Python correction preserves identical ASTs. The iOS app now exact-pins and explicitly links `swift-sharing` `2.9.1`, imports the defining module, and freezes the generated product reference in package/release-surface checks. A replacement hosted run remains required; the failed run is not GREEN evidence.
- [ ] Task 3 revocable account vertical slice: behavior-first backend identity/session/tombstone migration, dual-mode compatibility, generated Product API, AuthenticationServices/Keychain integration, hosted iOS compile/tests, a booted local iPhone Simulator walkthrough with surfaced screenshots/recording and visual score `>= 90`, and independent security/privacy/spec/architecture/reuse/UX review.
- [x] Supersede M0 and production-scale metrics as aggregate development gates per the 2026-07-28 active Goal update; preserve the research assets as an optional truthful future track while continuing all Tasks 2–10.

## Surprises & discoveries

- The original main worktree's recurring dirty state was generated evidence, not remote divergence. One useful post-merge E2E selector adjustment was preserved in a recoverable stash; main is clean and aligned.
- Existing backend assets are substantially more reusable than the H5: Item/Look, capture, outfit constraints, render lifecycle, ownership, jobs, LiteLLM and cost guards form a credible product core.
- The current anonymous 30-day HMAC cookie cannot provide commercial revocation or account deletion; it must not be reused as the native account contract.
- Current H5 stores person photos/body data in `localStorage`; native storage must not copy that design.
- M0 needs a local repository-side operating surface before real external market operations and decision claims. The implemented surface validates only de-identified aggregate records; it intentionally does not fabricate cohort, payment, refund, or maturity evidence, and the absence of those real records no longer blocks local native iOS/backend development.
- China-market operating controls tighten M0 collection: recruit toward 30 to preserve a mature denominator, cap natural search at <=50%, approved women/travel groups at <=35%, second-degree referrals at <=25%, and professional creators at <=20%; exclude bounties, volume-paid group owners, information-feed ads, positive-feedback rewards, and completion cash rewards.
- The 2026-07-28 external-readiness audit found no established Xiaohongshu creator login signal, authorized legal-subject/contact values, group-forward approvals, merchant/refund authority, isolated refund reserve, or controlled external evidence register. One direct read-only navigation attempt in each available browser surface produced no usable page or login-state signal; no external side effect was attempted. This is recorded in `docs/research/journey-validation/external-readiness.md` and blocks real external M0 launch operations that need those inputs; it does not block local iOS/backend implementation, Apple sandbox, staging, or TestFlight technical verification.

- Current FASHN default would send person photos overseas and FastFit is non-commercial. Removing P0 try-on improves both compliance and margin without weakening the paid Journey job.
- StoreKit official client/server libraries cover the first launch; RevenueCat is not necessary until cross-platform or remote-paywall operations become real bottlenecks.
- TCA `1.26.1` is the approved mature iOS app shell. Task 2 must prove AppFeature/AppView, feature reducers, dependency clients, cancellation, navigation restoration and TestStore ergonomics before broad feature work; do not resurrect custom Router/Environment/ViewModel architecture.
- SwiftPM resolution under Xcode 26.5 / Swift 6.3 rejects `swift-openapi-generator` 1.13.0 when `swift-openapi-runtime` is forced to 1.9.0 because generator 1.13.0 disables runtime default traits and runtime 1.9.0 predates trait declarations. Official manifests show generator 1.13.0 requires runtime from 1.11.0 with `traits: []`, and runtime 1.11.0 introduces the `FullFoundation` default trait. Task 2 corrects only the runtime exact pin to 1.11.0 and keeps URLSession transport at 1.1.0 pending throttled xcodebuild verification.
- Task 2 exposed a review-process gap: prior static/source review treated the iOS slice as source-clear before hosted Swift compilation. That was a false-clear. A Task 2 source review cannot be final-clear unless a matching local or hosted Swift compile/test run has passed for the reviewed HEAD.
- Task 2 review-fix round 1 exposed three evidence-quality gaps: direct application `UserDefaults` usage requires an executable privacy manifest check for `NSPrivacyAccessedAPICategoryUserDefaults` reason `CA92.1`; navigation persistence failures must be observable instead of being swallowed behind `try?`; and bulky raw CI logs are not acceptable tracked evidence when run/job URLs plus compact snippets suffice. Task 3 then removed the app-owned `UserDefaults` navigation store, so the app manifest must not keep `CA92.1`; dependency package manifests still carry their own audited `C56D.1` and `C617.1` declarations.
- The current Journey shell has no nested navigation stack. Restoration persists the selected tab and optional Journey ID in `NavigationSnapshot`; adding `StackState` now would invent state that the UI does not yet drive.
- `swift package show-dependencies` is not applicable to this generated Xcode project because there is no `Package.swift`. The accepted equivalent evidence is hosted `xcodebuild -resolvePackageDependencies`, exact `Config/Package.resolved` version/revision checks, generated `project.pbxproj` package-product checks and post-resolution lock byte checking.
- The repeated hosted iOS failures were not one bug. The convergence chain was: non-interactive OpenAPI build-plugin trust, then this XcodeGen/Xcode 26 project's missing direct link products for object-file `Dependencies`/`CasePathsCore` references plus invalid TestStore trailing-label syntax, then Swift 6 XCTest actor/autoclosure rules. The final green evidence is run `30317565521`.
- The first uncommitted Task 3 exploration produced 14 passing focused tests while still allowing access-token expiry to disable refresh, collapsing unrelated repository failures into authorization-code replay, silently swallowing Keychain failures, omitting Apple authorization-code exchange/hashed-nonce semantics, and leaving TCA/credential-revocation/tombstone write boundaries unproved. Those 14 tests are characterization only, not milestone evidence. Task 3 now requires behavior-specific RED proofs and a frozen hosted Swift GREEN before any source-clear claim.
- The 2026-07-29 unified Task 3 review found that removing duplicate infrastructure was necessary but insufficient: live test defaults could still invoke Apple UI, cancellation was converted into business failures or an allow-path `.unavailable`, revoked credentials could surface the wrong recovery UI, raw bearer secrets remained in TCA observable state, the backend discarded Apple's revocable provider grant, and `202 Accepted` deletion copy claimed completed erasure. Focused RED coverage now freezes each defect. These findings are part of Task 3 acceptance and must be repaired before hosted GREEN, simulator evidence, or milestone approval.
- A synchronous "call Apple, then revoke locally" deletion order cannot guarantee the user-visible `202`, cannot recover from Apple outages, and races with grant replacement. Task 3 therefore commits the local freeze/session revocation/idempotency record and encrypted revocation work atomically, then lets a narrow maintenance worker retry Apple outside the request. Likewise, a bearer-authenticated deletion-status endpoint is unusable after that same transaction revokes the bearer; the current route was removed and M6 owns a future receipt-scoped convergence query.
- The 2026-07-28 `origin/main` restyle is an H5 visual refresh, not a Journey information architecture. Its improved lavender hierarchy, solid pale-purple shadows, accessible inactive text, card density and bottom action-sheet treatment are useful references. The six-destination navigation, Feed return paths and combo-wardrobe structure do not fit the paid 3–7 day Journey job. The current native Journey screen is only a neutral foundation, so future native screens will use a Journey-specific composition while adopting the better new-main visual tokens where they outperform the placeholder tokens; no old-main UI is to be preserved by accident.
- Task 3 RED proofs confirmed three concrete defects in the exploratory implementation: access expiry disabled refresh, deleted subjects were reported as authorization-code replay, and an already-bound account could be rebound to a second Apple subject. The repaired policy uses an absolute refresh deadline preserved across rotation and typed domain failures; focused account regression is 18/18, while no milestone completion is claimed.
- Apple Swift OpenAPI Generator `1.13.0` warns on and skips OpenAPI 3.1 `type: null`, which silently removed FastAPI optional business properties from generated Swift. The canonical H5 OpenAPI remains unchanged; the iOS input now uses a deterministic projection that collapses only exact `anyOf: [T, null]` pairs and relies on existing `required` metadata for optionality. Regression tests preserve real unions and the generator-input check rejects any remaining nullable `anyOf`. Separately, OpenAPI requires plain `Authorization` header parameters to be ignored; authenticated calls therefore use Apple OpenAPI Runtime's documented `ClientMiddleware` bearer pattern rather than a handwritten transport DTO or another schema rewrite.
- Hosted run `30393350600` showed that re-exported `@Shared` APIs can compile while the generated Xcode app target still omits the `Sharing` product at link time. Because `AppFeature` directly uses `Shared` and `.fileStorage`, this XcodeGen/Xcode 26 project must expose the already-resolved exact `swift-sharing` product explicitly; this is a linker boundary correction, not a second state framework or a license/privacy expansion.
- Task 2 review-fix round 1 produced a separate quality lesson: a GREEN run that is still opaque can be cancelled and replaced by a more diagnosable run, but that cancellation must be recorded explicitly and must not be counted as a code failure or a proof. The replacement proof is run `30319519482`, which passed after CI split `xcodebuild -resolvePackageDependencies`, package graph validation, simulator tests, lock checking and privacy/boundary checks into separate steps.
- Task 2 review-fix round 1 also exposed a process error: run `30319082666` was a GREEN candidate, but a diagnostic CI commit was pushed before the candidate completed and the old run was then intentionally cancelled. That made the candidate evidence unusable. Future GREEN candidates freeze both HEAD and CI workflow until completion; cancellation/replacement is allowed only after a documented timeout, no-log threshold, or explicit evidence-quality threshold.
- Fresh baseline verification exposed one pre-existing H5 test that synchronously asserted content hidden behind an asynchronous wardrobe load. The test now waits for the observable card before checking terminal removal; production behavior was unchanged and all 239 JavaScript/Skill plus 301 Python tests pass.

## Decision Log

- 2026-07-28: Keep TCA exact-pinned at public stable `1.26.1` for Task 3/P0 after the required pre-M2 audit. The current app already uses modern 1.x reducers/stores/dependencies and no public reproducible stable TCA 2.0 tag exists; do not make the account milestone depend on beta/private APIs. Reopen when Point-Free publishes a public reproducible 2.0 package or local deprecated APIs create measured pressure.
- 2026-07-29: Keep authentication secrets outside TCA observable state. `AuthClient` and its Keychain/server adapters own Apple, access, and refresh tokens and return only a secret-free authenticated-account summary to reducers and views. Preserve `CancellationError` unchanged through Product API, credential-state, Keychain, and TCA effects; fail-closed test dependencies must never invoke live Apple UI.
- 2026-07-29: Treat Sign in with Apple revocation and account deletion as one server-owned durable lifecycle. Retain the minimum Apple access and refresh grant behind encrypted storage; atomically freeze/tombstone the subject, revoke local session families, record idempotency, and enqueue every revocable grant before returning `202`; perform Apple revocation only in the maintenance worker with exact-success, lease/CAS, retry and ciphertext-wipe rules. Represent `accepted`/`frozen` as processing. Only verified cross-system erasure may be described as completed deletion.
- 2026-07-29: Persist a secret-free iOS deletion intent and stable idempotency key before the delete call. A network failure may retry with the same bearer/key while tokens remain; an accepted or ambiguous `202` removes normal authentication from the app shell and restores only into deletion reconciliation or local-cleanup recovery. Do not add a normal bearer-authenticated deletion-status endpoint; M6 must use a scoped deletion receipt/capability.
- 2026-07-28: Use PyJWT `[crypto]` `2.13.0` / `7144e4534c34810f4525dc4578a32addd8212cff` as the sole JOSE implementation for Apple RS256 identity-token verification and ES256 client-secret signing. Reuse the existing locked cryptography/httpx stack; forbid token-controlled key URLs/algorithms, keep the JWKS endpoint fixed, and keep nonce, authorization-code replay, canonical binding, rotating sessions, revocation and deletion as application/domain policy behind `AppleIdentityVerifier`.
- 2026-07-28: Correct the iOS OpenAPI runtime exact pin from 1.9.0 to 1.11.0 for SwiftPM traits compatibility with Apple Swift OpenAPI Generator 1.13.0. This preserves the required generator 1.13.0 pin and exact dependency policy without broadening to ranges or branches.
- 2026-07-28: Product-owner correction: M0 repository infrastructure is implemented locally and the market decision remains `BLOCKED_FOR_REAL_EVIDENCE`, but Task 2 native iOS work is admissible for local development, Apple sandbox, staging, and TestFlight technical verification. Real cohort, ¥12 refundable deposits/payments, refunds, complete concierge plan outcomes, and `trip_end+7d` execution evidence remain mandatory before any M0 `GO`/`PIVOT`/`STOP`, production commercialization, scale, or aggregate-completion claim.
- 2026-07-28: Supersede the earlier M0/scale completion gate. The active Goal now requires continuous completion of Tasks 2–10 and M1–M7; M0 recruitment, payment, maturity denominators and production conversion/scale thresholds are optional market-learning inputs, not blockers for development, TestFlight, release readiness or aggregate completion. Technical evidence still must not be misreported as real production behavior.
- 2026-07-28: Record external execution readiness separately from product validation. Missing authorized account, legal-subject/contact, merchant/refund, reserve and controlled-data-store evidence prevents safe recruitment or deposit collection; it is not a failed product experiment and does not authorize `PIVOT` or `STOP`.
- 2026-07-28: Adopt TCA `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978` as the mature app shell and reject custom Router/Environment/ViewModel infrastructure; SwiftUI/Observation remain rendering/lifecycle only.
- 2026-07-29: Restore navigation through TCA Sharing instead of a custom persistence client. `NavigationSnapshotClient`, app-owned `UserDefaults`, the navigation persistence effect and status are removed; `@Shared(.fileStorage)` persists the pure `Codable` snapshot, and `AppFeature` owns restore/deep-link state. Do not add `StackState` until a real pushed navigation stack exists. Because application code no longer directly uses `UserDefaults`, `PrivacyInfo.xcprivacy` no longer declares app-owned `CA92.1`; the TCA/swift-sharing manifests continue to cover their own `C56D.1` and `C617.1` required-reason APIs.
- 2026-07-29: When an application target directly uses TCA's re-exported `Shared`/`.fileStorage` symbols, exact-pin and link `swift-sharing` explicitly in this generated Xcode project and import its defining module. Keep the dependency feature-local and do not generalize this into linking every transitive TCA product.
- 2026-07-28: Add a Task 2 development gate: after three consecutive hosted iOS failures, stop incremental fixes and require a fresh debugger pass with full hosted log root-cause mapping, plus independent dependency review before treating direct package-product exposure as architectural precedent. Uncompiled Swift is never `source-clear`.
- 2026-07-28: For Task 2 XcodeGen dependency evidence, replace `swift package show-dependencies` with Xcode-project evidence because the project has no `Package.swift`: hosted `xcodebuild -resolvePackageDependencies`, `Config/Package.resolved` exact pin/revision validation, generated `project.pbxproj` product-reference validation and `bootstrap_ios.sh --check-package-resolved`.
- 2026-07-28: Treat CI observability as a quality gate for hosted iOS verification. Monolithic macOS steps may be replaced with split dependency-resolution, package graph, simulator test, lock and privacy/boundary steps; an intentionally cancelled superseded run must be documented with the replacement run/job IDs and cannot be counted as either a code failure or a GREEN proof.
- 2026-07-28: Freeze HEAD and CI workflow after dispatching a GREEN candidate until that candidate completes. Do not push diagnostic CI commits while the candidate run is still in progress. Cancel and replace only after a documented timeout/no-log/evidence-quality threshold; record the cancellation reason and replacement run ID.
- 2026-07-28: Harden the Task 3 account contract before implementation: Apple sign-in must hash the raw nonce for the identity-token claim and exchange the one-time authorization code through the fixed Apple token endpoint; access and refresh lifetimes are distinct; repository failures use typed classifications; Keychain operations are throwing; AuthenticationServices and the generated Product API are TCA dependency clients; deletion is enforced again at repository, job-finalization and owner-scoped object-write boundaries rather than relying only on HTTP authentication.
- 2026-07-28: Scope the direct `Dependencies`/`CasePaths`/`Clocks` product exposure to this XcodeGen + Xcode 26 generated project. It is the minimum fix for the observed link command and app/test object-file references, not a general statement that TCA 1.26.1 applications must explicitly link every transitive product.
- 2026-07-28: Keep FastAPI's OpenAPI 3.1 document canonical for H5 and derive a Swift-only compatibility projection at export time. Collapse only exact nullable two-member unions because generator `1.13.0` otherwise drops those fields; do not handwrite DTOs, mutate backend contracts, or flatten real unions.
- 2026-07-28: Audit the refreshed `origin/main` UI before native Journey screen implementation. Keep independently designed Journey flows, replace any inherited old-main styling, and selectively reuse the new lavender palette, solid soft-shadow system, accessible secondary text and bottom-sheet interaction. Do not import Feed navigation or the six-tab H5 shell. Verify the decision on real iOS Simulator screenshots, not SwiftUI previews alone.
- 2026-07-27: Make scene execution, not content consumption, the first paid result.
- 2026-07-27: Target native iOS 17+ and reuse the existing Product API rather than wrapping H5 or rebuilding backend services.
- 2026-07-27: Price one Journey pack at a ¥12 hypothesis and show the contextual paywall after one complete Day 1 travel result.
- 2026-07-27: Use GRDB, Swift OpenAPI Generator and Nuke as the only initial external client dependencies.
- 2026-07-27: Keep StoreKit entitlement verification in the existing Python backend using Apple's maintained server library.
- 2026-07-27: Forbid overseas person-photo processing and photorealistic try-on in China-first P0.
- 2026-07-27: Require the M0 seven-day recruiting/offer window plus post-trip maturity evidence before production commercialization, paid production scale, or aggregate completion claims, and use frozen mature cohorts for scale decisions.
- 2026-07-27: Do not count TestFlight/sandbox transactions as commercial evidence; require production cohorts with frozen denominators.
- 2026-07-27: Keep subscription secondary until 60-day second-paid-Journey behavior reaches 25%; preserve pack restore and read-only access without Pro.

## Outcomes & retrospective

Not started. Complete after each milestone with observed user outcome, quantitative result, verification evidence, remaining risk, and the resulting continue/pivot/stop decision.
