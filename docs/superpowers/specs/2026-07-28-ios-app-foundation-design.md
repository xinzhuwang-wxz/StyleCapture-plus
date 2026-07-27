# iOS App Foundation Design

- Date: 2026-07-28
- Status: approved design direction; local implementation may proceed; M0 GO remains a market/commercialization gate
- Scope: `apps/ios/StyleCaptureJourney` architecture planning only

## Sources Of Truth

This spec supports and sharpens the active Goal launch prompt and `docs/exec-plans/0043-stylecapture-journey-commercial-app.md`. If implementation task briefs drift, preserve the Goal and ExecPlan first, then update the lower-level brief to match this TCA-native foundation.

## Decision

Use The Composable Architecture (TCA) `1.26.1` as the production app shell and write only the StyleCapture Journey business kernel. Pin `pointfreeco/swift-composable-architecture` to release `1.26.1`, tag commit `ead11e04e5011c437722c1990d22f80d87056978`, MIT license, with the official repository and release as audit sources:

- https://github.com/pointfreeco/swift-composable-architecture
- https://github.com/pointfreeco/swift-composable-architecture/releases/tag/1.26.1

TCA owns app-level state, feature composition, navigation state, effect execution/cancellation, dependency injection through dependency clients, and reducer-level tests through `TestStore`. SwiftUI and Observation remain the rendering layer. The app still uses XcodeGen `2.46.0`, generated OpenAPI, GRDB, Nuke, StoreKit 2 plus Apple's server library, Sign in with Apple, Apple lifecycle/testing frameworks, OSLog, MetricKit, Xcode Cloud and TestFlight.

## Approaches Considered

### A. TCA shell plus mature components

Adopt TCA as the shell and compose it with the mature components already selected for the app. This is the recommended path because it removes custom navigation, environment, effect and test harness design from the P0 scope while preserving pure StyleCapture Journey domain policies.

Ownership boundary:

- We write Journey domain entities, policies, invariants, feature reducers, dependency client protocols and thin Core adapters.
- TCA owns reducer composition, store lifecycle, navigation state, dependency injection, effect cancellation and `TestStore` assertions.
- SwiftUI/Observation owns rendering and state observation at the view boundary.
- XcodeGen owns project generation; Apple Swift OpenAPI Generator owns Product API clients; GRDB owns SQLite/offline projection/outbox; Nuke owns image loading/caching; StoreKit 2 and Apple's App Store Server library own purchase protocol surfaces; Apple frameworks own auth, Photos, background tasks, notifications, diagnostics, tests and release lifecycle.

### B. SwiftUI/Observation custom shell

Rejected. SwiftUI, Observation, structured concurrency and NavigationStack are still used, but hand-rolling `AppRouter`, `AppEnvironment`, effect cancellation, dependency overrides and state restoration would make the app shell too DIY. That path spends P0 engineering budget on framework problems instead of the travel planning, packing, entitlement, offline and recovery kernel.

### C. Hosted turnkey BaaS or subscription stack

Rejected for China-first P0. Firebase, Supabase, Amplify and RevenueCat duplicate the existing FastAPI/PostgreSQL/Celery/LiteLLM backend responsibilities or add US data/vendor surfaces. RevenueCat's official DPA says the service operates on AWS and its processing addendum/subprocessor model adds a separate purchase-data processor; the user-provided upstream evidence records customer data sent to AWS data centers in the United States. The P0 path stays with StoreKit 2, Apple's server APIs/libraries and our existing ledger. Revisit only after a measured cross-platform entitlement, remote paywall or operations bottleneck and after in-region privacy controls are proven.

Sentry Cocoa is not a default P0 dependency. OSLog, MetricKit and App Store diagnostics are the baseline. Sentry may be reconsidered only as a release-gated crash candidate after in-region or self-hosted privacy controls, DPA/processor review, data minimization and deletion propagation evidence.

## Module Layout

```text
apps/ios/StyleCaptureJourney/
  App/
    StyleCaptureJourneyApp.swift
    AppFeature.swift
    AppView.swift
  Core/
    API/
    Auth/
    Background/
    Database/
    DesignSystem/
    Entitlements/
    Images/
    Notifications/
    Observability/
    Photos/
  Features/
    Onboarding/
    Wardrobe/
    Journey/
    Packing/
    Paywall/
    PixelJournal/
    Settings/
  OpenAPI/
  StoreKit/
  StyleCaptureJourneyTests/
  StyleCaptureJourneyUITests/
  Resources/
```

Each feature owns its TCA reducer, state, action and view. Pure domain rules live in a feature-local `Domain` group or `SharedDomain` only when the rule is substantial or shared; do not force every feature to contain domain/application/infrastructure/interface layers. External adapters live only under `Core/*`. Reducers orchestrate pure rules and effects but do not become the source of server truth.

## Dependency And Effect Rules

- Pin all SwiftPM packages to exact versions or revisions in `project.yml` and lock them in `Config/Package.resolved`.
- Use TCA dependency clients for Product API, GRDB, StoreKit, SIWA, Photos import, background scheduling, notifications, image loading, OSLog/MetricKit and clocks/UUIDs.
- Effects must be cancellable when tied to view/task/navigation lifetime.
- Reducers may call dependency clients and pure domain services; views may send actions and render observed state only.
- `StyleCaptureAPI` generated DTO imports are allowed only in the `Core/API` adapter and its tests. Reducers, domain rules and application-like policies consume dependency clients returning domain values and typed errors.
- Feature UI must not import infrastructure adapters or generated transport DTOs directly.
- Server truth remains in FastAPI/PostgreSQL; local GRDB state is a projection/outbox and entitlement cache only.

## Data Flow

1. SwiftUI views send typed TCA actions.
2. Feature reducers validate local state transitions, call pure Journey policies and start dependency effects.
3. API effects call the generated OpenAPI client through a dependency client.
4. GRDB effects update local projections and outbox records.
5. StoreKit effects emit purchase events; backend Apple verification and the entitlement ledger are the source of truth.
6. Reducers receive success/failure actions and update user-visible recovery state.

## Error And Recovery Model

- Every external dependency returns typed domain-facing errors with a user-recoverable category: retry, sign in, restore purchase, permission recovery, offline wait, local cleanup, contact support or server reconciliation.
- Reducers own visible error state and recovery actions.
- Outbox retries are idempotent and preserve user edits.
- BackgroundTasks expiration, denied scheduling and relaunch are modeled as reducer events and tested.
- Purchase failure never consumes paid units; refund/revocation/reconciliation flows come from server truth.

## Testing

- Use TCA `TestStore` for reducer flows, dependency overrides, navigation restoration, cancellation and failure/recovery assertions.
- Use Swift Testing for pure domain/application policies.
- Use XCTest/XCUITest for launch, permissions, StoreKit configuration, accessibility, Dynamic Type, offline/weak-network and background behavior.
- Task 2 must prove compile/test ergonomics with a small AppFeature and at least one feature reducer before broad feature work.

## Versioning And Migration Guard

TCA is pinned to `1.26.1` / `ead11e04e5011c437722c1990d22f80d87056978`. Use current non-deprecated APIs only. Because TCA has API churn toward 2.0, add a pre-M2 migration audit before expanding feature work: check deprecations, release notes, dependency syntax, navigation APIs, TestStore changes and compile impact. A later TCA 2.0 migration requires an ADR and a measured benefit or compatibility need.

## Non-Goals

- No production commercialization, paid production rollout, scale claim, aggregate Goal completion, or M0 `GO`/`PIVOT`/`STOP` claim before real M0 evidence matures. Local implementation, Apple sandbox, staging, and TestFlight technical verification may proceed and must stay out of M0 and production commercial denominators.
- No custom `Router`, global `Environment`, ViewModel architecture, DI container or navigation framework.
- No Tuist until project graph/caching/selective-test pain is measured.
- No Firebase, Supabase, Amplify or RevenueCat for China-first P0.
- No second backend, generated API clone, image cache, sync database, purchase verifier, telemetry backend or agent framework.
- No GitHub Issue or PR actions under this planning task.
