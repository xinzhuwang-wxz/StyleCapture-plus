# Journey Skill / Agent Capability Registry

- Status: planning baseline
- Product truth: FastAPI Journey application modules and versioned Product API
- P0 distribution: native iOS app only; no public downloadable agent Skill

## Why current Skills are not commercial product architecture

The current repository uses “Skill” for incompatible surfaces:

- `scene-outfit-matching` is a safe but legacy single-scene `/v1/outfit-plans` wrapper.
- `real-photo-flat-lay-collage` is a safe but render-only helper.
- `doubao-virtual-try-on` is a provider-bound standalone Codex artifact allowed by ADR 0006; it directly handles provider models, keys, prompts and local photos and is not a Product API capability.

Their tests correctly prove wrapper/audit behavior, but they do not prove the commercial Journey domain, entitlement, outbox/inbox, deletion, cost reservation, provider gateway, production observability or iOS recovery. The fix is not a longer prompt. It is a governed capability boundary.

## Invariants

1. A Skill, App Intent, CLI or future MCP tool is only an interface adapter. The server application use case owns rules, workflow state, persistence, entitlement, idempotency, cost and provider access.
2. No Journey interface adapter contains prompts, wardrobe truth, ranking rules, provider IDs/endpoints/keys, StoreKit verification, SQL, COS access or Celery calls.
3. TypeScript adapters use a shared `openapi-typescript` + `openapi-fetch` generated package; Swift uses Apple Swift OpenAPI Generator. No adapter hand-maintains DTOs.
4. P0 has no public downloadable Skill. A future external Skill/MCP gateway is release-blocked until scoped delegated authentication, explicit user authorization, consent, revocation, rate/cost limits, deletion and App Review/legal analysis pass. It may never auto-create an anonymous cookie for paid or personal operations.
5. The existing provider-bound Doubao Skill and its output are excluded from Journey runtime, production evidence and China P0. Moving that behavior into the product requires a normal provider adapter, consent/data-residency review, entitlement/cost/deletion controls and Promptfoo gates; the standalone script is not reusable runtime infrastructure.
6. Apple App Intents/Shortcuts, when added after the paid core works, call the same iOS application services/generated client and expose only low-risk, user-confirmable actions. They do not accept open-ended prompts or run a parallel planner.

## Capability contract

| Capability ID | Product API / owner | Auth and entitlement | Idempotency / async | Deletion and quality |
|---|---|---|---|---|
| `journey.create` | `POST /v1/trips` / `trip_planning` | revocable account session; no paid entitlement | idempotency key; synchronous accepted state | subject-owned; deletion tombstone checked; schema/rule tests |
| `journey.select_wardrobe` | `POST /v1/trips/{id}/wardrobe-selection` / `trip_planning` | owner-scoped selected Item IDs | version + idempotency; ownership conflicts explicit | no copied Item truth; cross-account tests |
| `journey.preview_day1` | `POST /v1/trips/{id}/plans` + job status / `trip_planning` | free preview eligibility only | `202` durable job, outbox/inbox, retry/dead-letter | Day 1 main Look only; Promptfoo quality/privacy gate; no fixed fallback |
| `journey.read_paid_plan` | `GET /v1/trips/{id}` / `trip_planning` | verified pack for this Journey | cached versioned read | returns `PAYWALL_REQUIRED` without leaking locked details |
| `journey.replace_slot` | `POST .../replace` / `trip_planning` | verified pack for this Journey | version + idempotency; may return durable job | locked-slot invariants; cost reservation; trace metadata only |
| `journey.lock` | `POST .../lock` / `trip_planning` | verified pack | version + idempotency | immutable revision/audit; plan-lock event |
| `journey.packing` | `GET/PATCH` packing endpoints / `trip_planning` | verified pack; restore reproduces access | offline outbox + version conflict | owner-scoped; deletion cascade; packing-proxy VSS |
| `journey.weather_refresh` | `POST .../weather-refresh` / `trip_planning` | verified pack and refresh allowance | cost/usage reservation + durable job | source/time provenance; locked revision preserved |
| `journey.complete` | `POST .../complete` / `trip_planning` | owner + verified pack | idempotent | confirmed-worn VSS requires explicit adoption evidence |
| `account.deletion_status` | `GET /v1/account/deletion-status` / `account` | revocable account session | read-only retryable stages | no internal/sensitive payload; convergence evidence |

Store purchase is deliberately absent: external Skills and App Intents cannot bypass StoreKit or simulate entitlement. The native App owns purchase presentation and Apple transaction handoff.

## Evidence required before any external Skill release

- Generated-client diff proves every request/response is derived from current OpenAPI.
- Contract journey proves create → selection → Day 1 preview → `PAYWALL_REQUIRED` → verified unlock → replace → lock → offline packing → completion, including 202 polling, retry and version conflict.
- Architecture scan finds no provider endpoint/model/key, prompt, database/storage/queue client, StoreKit verification or copied business rule in Skill/App Intent sources. ADR-0006's isolated legacy directory is the only explicit scan exception and remains excluded from product evidence.
- Auth tests cover scope, PKCE/device authorization if adopted through a mature library, revocation, expiry, cross-account access and lost-device recovery.
- Promptfoo and real-provider tests execute the Product API capability, never the facade as a fake inference provider.
- Pack entitlement, cost reservation, deletion propagation, privacy canary and production trace evidence match the native App path.

## Future mature reuse

- iOS: Apple App Intents, App Shortcuts and Shortcuts confirmation UI.
- TypeScript facade: existing `openapi-typescript` and `openapi-fetch`, moved into one generated workspace package shared by H5/internal harness/future Skill.
- External agent protocol: evaluate the official MCP SDK or direct OpenAPI tool exposure only after delegated-auth and product demand are measured; do not hand-build a tool protocol.
- OAuth/delegation: select a maintained OAuth 2.1/OIDC library and authorization server only when public agent access becomes an approved product, with a separate reuse/security ADR.
