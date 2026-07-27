# ADR 0007: Build Journey as a native iOS client over the existing Product API

- Status: accepted for validation
- Date: 2026-07-27
- Decision owners: StyleCapture Journey commercial branch

## Context

The commercial product is no longer a Douyin Feed experience. Its first paid job is one private 3–7 day travel plan that combines wardrobe assets, weather, constraints, packing, purchases, offline access, Apple payments, and completion reminders. Single-day wedding, interview and date jobs remain separate future experiments so their demand and conversion are not aggregated with travel. Reusing the H5 shell would preserve code but would not provide the best Photos, StoreKit, background, notification, accessibility, or App Store conversion integration.

The repository already contains the valuable server-side assets: Item/Look truth, capture processing, outfit constraints, LiteLLM reranking, render artifacts, cost guards, ownership, jobs, and OpenAPI. Rebuilding these services for a new client would create divergent truth.

## Decision

Create `apps/ios/StyleCaptureJourney` as an iOS 17+ SwiftUI application using Observation and Swift Concurrency. Use GRDB for explicit offline persistence/outbox, Apple Swift OpenAPI Generator for the Product API client, and Nuke for image loading. All other default client capabilities use Apple frameworks: Sign in with Apple, PhotosPicker/CoreTransferable, UniformTypeIdentifiers, ImageIO, Vision OCR, WeatherKit after coverage smoke, StoreKit 2, BackgroundTasks, Network/NWPathMonitor, UserNotifications, OSLog, MetricKit, Swift Testing, XCTest, XCUITest, NavigationStack, and Xcode Cloud/TestFlight.

Generate the Xcode project from an audited XcodeGen `project.yml`; do not hand-maintain or commit `.xcodeproj`. Tuist remains a measured-scale option, not a P0 service dependency.

Keep the FastAPI modular monolith. Add durable Trip/Occasion/Packing and Store entitlement modules that reference existing Item, Look, OutfitPlan, and RenderArtifact records. Do not duplicate wardrobe or recommendation logic in Swift.

Use StoreKit 2 plus Apple's App Store Server Python library and Notifications V2. RevenueCat is not a P0 dependency because the product is iOS-only and China-first; external purchase-data processing, vendor cost, and lock-in do not yet buy enough value. Reconsider it only if cross-platform entitlement and remote paywall operations become a measured bottleneck.

P0 product analytics uses first-party, schema-controlled events plus App Store Connect Analytics. No IDFA, session replay, autocapture, photo content, itinerary text, or precise location enters analytics.

Treat Skill/App Intent/agent surfaces as interface adapters over governed Product API capabilities, never as the intelligence architecture. P0 ships no public Journey agent Skill. The current direct-provider Doubao Skill remains an ADR-0006 standalone tool and is excluded from Journey runtime/evidence. Later native shortcuts use Apple App Intents over the same application/generated-client path; later external agent access must reuse generated OpenAPI or an official MCP SDK plus mature delegated authentication rather than ad-hoc scripts.

Use the repository's production AI stack rather than creating a second orchestration layer: LiteLLM Proxy for gateway/routing/budgets, Celery/Redis plus PostgreSQL outbox/inbox for durable jobs, pgvector for owned-item retrieval, Promptfoo for isolated CI evaluation/red teaming, and OpenTelemetry. Before soft launch, deploy an in-region Langfuse edition/control model that proves retention, audit, RBAC, private access and deletion. Reject the default LiteLLM callback that records model input/output; emit only allowlisted metadata through a fail-closed sanitizer and a second Collector drop policy. OSS may be used only when external controls close its retention/audit/RBAC gaps with automated evidence. Do not add LangChain/LlamaIndex/general agent orchestration until an actual open-ended tool/RAG workflow exists.

For the China-first P0, disable FASHN and every other overseas person-photo processor. Use deterministic real-item collage and pixel mementos unless a domestic provider passes contract, data-residency, no-training, deletion, labeling, and filing review. Sign in with Apple uses server-verified identity tokens and revocable server sessions; the existing anonymous HMAC cookie is not the commercial account contract. Account deletion is a cross-system state machine, not a row delete.

## Consequences

- The commercial App can evolve independently without merging quickly into the H5 product.
- Existing backend behavior remains one truth and is consumed through generated contracts.
- Native iOS work is not a port of React components; visual language and pixel assets can be adapted, business logic cannot be copied into views.
- GRDB adds one dependency but provides explicit migrations, queries, offline outbox, and testable synchronization.
- StoreKit server handling becomes our operational responsibility, but Apple's maintained library removes cryptographic/protocol reinvention.
- XcodeGen, generated OpenAPI contracts, LiteLLM, Promptfoo, Langfuse and OpenTelemetry replace hand-maintained project/API/gateway/eval/trace foundations; their versions, privacy behavior and licenses become release-audited dependencies.
- AI observability stores join the account deletion and data-retention boundary; trace-to-dataset copies, queues, caches, exports, object versions and backups cannot be treated as operational data outside privacy obligations.
- Initial analytics are intentionally narrower than a third-party product suite; a vendor is added only after the event/query bottleneck is measured.
- The launch scope intentionally gives up photorealistic virtual try-on; this avoids a non-commercial license and an unresolved overseas sensitive-photo path while keeping the paid Journey result intact.
- Security, privacy, AI labeling, APP filing, and account deletion evidence are release gates, not post-launch backlog.

## Rejected alternatives

- Wrap the H5 in WKWebView: weak native integration, harder purchase/privacy review, and no meaningful reuse of server-side contracts beyond what native can already consume.
- React Native/Expo: would retain TypeScript but introduce a bridge and third-party lifecycle for Apple-first capabilities without a confirmed Android roadmap.
- Rebuild backend as Firebase/Supabase: duplicates mature domain, provider, job, ownership, and cost-control work already present.
- Split microservices before launch: creates distributed consistency and operations cost without solving the missing Trip/Packing domain.
- SwiftData as the primary commercial store: convenient for simple object graphs, but less explicit than GRDB for migrations, sync metadata, outbox, and complex packing queries.
- Feed or community as the paid home: neither is the first verifiable paid outcome.
