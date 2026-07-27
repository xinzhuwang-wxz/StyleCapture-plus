# ExecPlan 0043: StyleCapture Journey Commercial App

> Living plan. Keep Progress, Surprises & Discoveries, Decision Log, and Outcomes current while the Goal is active.

- Branch: `codex/stylecapture-journey`
- Status: reviewed planning baseline; ready for Goal launch
- Date: 2026-07-27
- Product: StyleCapture Journey（衣程）
- Target: China-first native iPhone app, iOS 17+

## Observable outcome

A user with an upcoming 3–7 day trip can select at least 8 slot-covering garments she already owns (12–30 recommended), receive an executable day/activity outfit plan with alternatives and a deduplicated packing list, unlock Day 2–7 through a ¥12 Apple in-app purchase, recover the purchase on another device, and later confirm what she actually wore. The app remains useful under weak connectivity, never invents owned garments, and turns completion into a private pixel journey memento.

The first release is successful only when real users pay for and execute this result. A polished Feed, a large digital wardrobe, photorealistic try-on, or a pixel world without verified scene success does not satisfy the outcome.

## Scope

### P0

- M0 seven-day recruiting/offer validation plus post-trip maturity evidence for one paid 3–7 day travel job and one ¥12 offer.
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

The plan uses two sequential commitments:

1. **Prove willingness to pay cheaply.** Do not build the complete native product before the M0 seven-day recruiting/offer plus post-trip maturity gate. Concierge work may use manually reviewed plan generation, but research responses and metrics must be real and attributable.
2. **Build vertical commercial slices.** After the gate passes, each branch-local milestone task delivers an observable iOS journey through generated API contracts, domain, persistence, worker/provider boundaries, and production evidence.

Create or update milestone ExecPlans and SDD task briefs only after the Goal starts so their acceptance criteria reflect the final reviewed plan. Execute them in the dependency order below without pausing between completed branch-local tasks. Do not read, create, edit, comment on, close, or otherwise touch GitHub Issues or PRs without explicit future authorization.

## Milestones and branch-local task order

### M0 — Paid problem validation

Outcome: a seven-day recruiting/offer window followed by post-trip maturity produces a reproducible go/pivot/stop decision from 20–30 qualified travelers, at least 15 complete plans, and one ¥12 offer. The decision waits until at least 15 plan recipients reach `trip_end+7d` and records the actual maturity cutoff.

Acceptance:

- `pain_rate` uses all qualified interviewees who completed the pain question, denominator ≥20, and must be ≥60% at 7/10 or higher.
- `execution_rate` uses every plan recipient whose trip has reached `trip_end+7d`, denominator ≥15, and must be ≥50% for a planned main/alternative Look or traceable hard-constraint-preserving replacement; non-response counts as not executed.
- `real_paid_rate` uses all qualified complete-plan recipients shown the one ¥12 offer, denominator ≥15, and must be ≥33% with at least five real refundable payments/deposits. It excludes willingness, oral promises and equivalent commitments. Research payment stays outside any App binary and never becomes an external iOS purchase link.
- The evidence set records recruiting source, upcoming date, completion, offer outcome (`paid|declined|refunded`), payment/deposit evidence status, objections, maturity and actual plan execution; it never treats a WTP choice as success.
- Failure leads to a revised wedge or stop decision; it does not authorize more feature work.
- An M0 `STOP`/`PIVOT` closes the research milestone and blocks the aggregate launch Goal. Task 2 requires a newly authorized wedge or an explicit `GO`; the failed original launch Goal is never marked complete.

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

Outcome: after seeing Day 1, the user can buy a ¥12 Journey pack, recover it across devices, survive duplicate/refund/revocation notifications, and never lose or double-spend entitlement. Subscription is technically configured but cannot become the default CTA until the mature 60-day repeat gate passes.

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
- `GET /v1/account/deletion-status` exposes retryable stage progress without sensitive internal payloads.
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
- TestFlight metrics are technical only. Production soft launch needs at least 200 eligible paywalls and 20 real payers for initial validation; scale decisions need at least 500 eligible paywalls, 50 payers and mature D90 outcomes. The audited metric dictionary and any-trigger kill rules decide scale, iterate, pivot, or stop.
- Capacity changes follow the recorded p95/CPU/connection/queue/provider/budget/table-size triggers; no speculative service split.

## Reuse audit

Every milestone copies this table into its branch-local ExecPlan and adds exact inspected source commit/license before implementation.

| Capability | Candidates inspected | Decision | Constraint |
|---|---|---|---|
| App shell/state/effects/navigation/tests | TCA `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978` | Direct reuse | MIT; exact pin; current non-deprecated APIs; pre-M2 2.0 migration/deprecation audit |
| UI/rendering/concurrency | SwiftUI, Observation, Swift Concurrency | Direct reuse | iOS 17+; rendering/lifecycle only, not custom app shell |
| Xcode project | XcodeGen `2.46.0` / `8445e77` | Direct reuse | MIT; generated project, reviewable spec |
| Navigation | TCA navigation state over NavigationStack/NavigationPath | Direct reuse | No custom Router/navigation framework; reducer tests prove restoration/deep-link behavior |
| Offline DB/outbox | GRDB.swift `v7.11.1` / `b83108d` | Direct reuse | MIT; explicit migrations and sync metadata |
| API contracts | FastAPI OpenAPI + Apple Swift OpenAPI Generator `1.13.0` / `af9a2a1` | Direct reuse | Apache-2.0; generated during build |
| Image pipeline | PhotosPicker/Transferable + Nuke `13.0.6` / `63a8fcb` | Direct reuse | No whole-library permission for selective import |
| Itinerary OCR | Apple Vision `VNRecognizeTextRequest` | Direct reuse | Device-side extraction; user confirms structured truth; raw screenshot stays local by default |
| Weather | Apple WeatherKit / WeatherKit REST | Candidate adapt | Gate on China city coverage, attribution, quota, server signing and degradation smoke; never invent forecasts |
| Purchase client/server | StoreKit 2 + Apple server Python `v3.1.2` / `4eaa224` | Direct reuse | Server ledger owns entitlement |
| Apple identity verification | AuthenticationServices + PyJWT `[crypto]` + Apple JWKS | Candidate direct/adapt | Re-audit stable release/license; never hand-write JOSE |
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
6. Real-user screenshots/video for initial, input, processing, success, failure, recovery, paywall, purchase and deletion states.
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
- [ ] Collect real M0 recruitment, payments/deposits, complete plans, refunds, post-trip follow-up, and maturity evidence outside Git.
- [ ] Record a real `GO`, `PIVOT`, or `STOP` in `docs/research/journey-validation/decision-log.md` only after at least 15 plan recipients reach `trip_end+7d`.

## Surprises & discoveries

- The original main worktree's recurring dirty state was generated evidence, not remote divergence. One useful post-merge E2E selector adjustment was preserved in a recoverable stash; main is clean and aligned.
- Existing backend assets are substantially more reusable than the H5: Item/Look, capture, outfit constraints, render lifecycle, ownership, jobs, LiteLLM and cost guards form a credible product core.
- The current anonymous 30-day HMAC cookie cannot provide commercial revocation or account deletion; it must not be reused as the native account contract.
- Current H5 stores person photos/body data in `localStorage`; native storage must not copy that design.
- M0 needs a local repository-side operating surface before native iOS work. The implemented surface validates only de-identified aggregate records; it intentionally does not fabricate cohort, payment, refund, or maturity evidence.
- China-market operating controls tighten M0 collection: recruit toward 30 to preserve a mature denominator, cap natural search at <=50%, approved women/travel groups at <=35%, second-degree referrals at <=25%, and professional creators at <=20%; exclude bounties, volume-paid group owners, information-feed ads, positive-feedback rewards, and completion cash rewards.

- Current FASHN default would send person photos overseas and FastFit is non-commercial. Removing P0 try-on improves both compliance and margin without weakening the paid Journey job.
- StoreKit official client/server libraries cover the first launch; RevenueCat is not necessary until cross-platform or remote-paywall operations become real bottlenecks.
- TCA `1.26.1` is the approved mature iOS app shell. Task 2 must prove AppFeature/AppView, feature reducers, dependency clients, cancellation, navigation restoration and TestStore ergonomics before broad feature work; do not resurrect custom Router/Environment/ViewModel architecture.
- Fresh baseline verification exposed one pre-existing H5 test that synchronously asserted content hidden behind an asynchronous wardrobe load. The test now waits for the observable card before checking terminal removal; production behavior was unchanged and all 239 JavaScript/Skill plus 301 Python tests pass.

## Decision Log

- 2026-07-28: M0 repository infrastructure is implemented locally, but the product decision remains `BLOCKED_FOR_REAL_EVIDENCE`. Task 2 native iOS work is still gated because no real cohort, ¥12 refundable deposits/payments, refunds, complete concierge plan outcomes, or `trip_end+7d` execution evidence exists.
- 2026-07-28: Adopt TCA `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978` as the mature app shell and reject custom Router/Environment/ViewModel infrastructure; SwiftUI/Observation remain rendering/lifecycle only.
- 2026-07-27: Make scene execution, not content consumption, the first paid result.
- 2026-07-27: Target native iOS 17+ and reuse the existing Product API rather than wrapping H5 or rebuilding backend services.
- 2026-07-27: Price one Journey pack at a ¥12 hypothesis and show the contextual paywall after one complete Day 1 travel result.
- 2026-07-27: Use GRDB, Swift OpenAPI Generator and Nuke as the only initial external client dependencies.
- 2026-07-27: Keep StoreKit entitlement verification in the existing Python backend using Apple's maintained server library.
- 2026-07-27: Forbid overseas person-photo processing and photorealistic try-on in China-first P0.
- 2026-07-27: Require the M0 seven-day recruiting/offer window plus post-trip maturity evidence before full P0 implementation and use frozen mature cohorts for scale decisions.
- 2026-07-27: Do not count TestFlight/sandbox transactions as commercial evidence; require production cohorts with frozen denominators.
- 2026-07-27: Keep subscription secondary until 60-day second-paid-Journey behavior reaches 25%; preserve pack restore and read-only access without Pro.

## Outcomes & retrospective

Not started. Complete after each milestone with observed user outcome, quantitative result, verification evidence, remaining risk, and the resulting continue/pivot/stop decision.
