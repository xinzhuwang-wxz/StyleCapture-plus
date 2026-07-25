# Look Render Artifacts ExecPlan

> **For agentic workers:** keep this plan current while Issue #5 is implemented.
> Complete the vertical slice on the integration branch without changing the state of
> PR #11, PR #12, Issue #4, or Issue #5.

**Goal:** Make every completed Look immediately presentable with a deterministic
collage of its real Item assets, then asynchronously add an honestly labelled
personal try-on or fixed-model preview and a StyleCapture pixel cover without turning
any generated image into garment truth.

**Architecture:** The approved pixel wardrobe is the presentation client. It consumes
stable Look and RenderArtifact APIs generated from backend OpenAPI. A feature-local
render module owns artifact lifecycle, caching, provenance and fallback. Provider
adapters remain private infrastructure details. The worker generates one artifact at
a time and stores bytes through the existing object store.

**Tech stack:** React 18, TypeScript, TanStack Query, FastAPI, Pydantic, SQLAlchemy,
PostgreSQL, Celery/Redis, Pillow, LiteLLM image capability, hosted try-on provider,
Vitest, Playwright and pytest.

## Ordering and integration contract

1. Keep Issue #3's real Feed, Item and Look behavior as the data foundation.
2. Integrate Issue #4's completed recommendation candidate without treating its
   playground fixtures as product data.
3. Adapt PR #12's approved first-level navigation and visual system to the real API.
4. Freeze the UI-facing RenderArtifact DTO from those real screens.
5. Implement collage, try-on and pixel-cover generation behind the DTO.
6. Test the combined mobile journey on this integration branch.
7. Do not merge or close teammate PRs or Issues without explicit user authorization.

This order is deliberate: the first-level product experience determines which
render states and actions must be visible, while the domain remains page-agnostic.
Issue #5 may extend the UI contract but may not replace it with a provider-specific
or mock-specific model.

## Product contract

- A Look card remains browsable before generated media is ready.
- The first successful artifact is a real Item collage and requires no model call.
- Saving an OutfitPlan creates the Look immediately, queues its collage and pixel
  cover independently, and returns control to the user. Each completed artifact is
  shown as soon as it succeeds; the client never waits for all selected Looks or all
  render kinds as a batch.
- Pixel cover and try-on are progressive enhancements, never prerequisites for saving
  or opening a Look.
- Personal try-on starts from a saved Look detail via “试穿这套”. On first use the user
  takes or uploads a consented full-body photo, confirms it, and applies that exact
  Look. Recommendation does not silently generate or imply a personal try-on.
- A personal try-on label is allowed only when the exact artifact used a user-approved
  reference photo. Otherwise the UI says fixed-model preview or Item collage.
- A failed or unsupported try-on remains failed/degraded and exposes the collage
  fallback; it is never relabelled as successful try-on.
- The pixel cover is a share-safe representation linked back to the exact Look.
- Item and Look remain the facts. RenderArtifact is disposable, reproducible output.
- No runtime mock, fixed response or procedural browser avatar may masquerade as an
  AI result.
- Public DTOs expose capability, artifact kind, status, fallback and privacy
  semantics. Provider and concrete model identities stay server-private.

## API shape

The backend OpenAPI is the source of truth. The H5 must use generated DTOs.

- `GET /v1/looks/{look_id}/renders`
  returns the user's artifacts for the Look.
- `POST /v1/looks/{look_id}/renders`
  requests an artifact kind and permitted presentation mode.
- `GET /v1/render-artifacts/{artifact_id}`
  returns current state and a private output route when available.
- `GET /v1/render-artifacts/{artifact_id}/image`
  streams authenticated bytes; clients do not receive object keys.
- Retrying creates or requeues according to the exact-input cache contract rather
  than copying a prior response.

The client needs:

- artifact id and Look id;
- kind: `collage`, `try_on`, or `pixel_cover`;
- status: `queued`, `running`, `succeeded`, `degraded`, or `failed`;
- presentation label and whether the result is personalized;
- output availability and authenticated image URL;
- fallback artifact reference when degraded;
- retryability and a safe failure code;
- created and updated timestamps.

## Progress

- [x] 2026-07-25: Issue #3 merged to main and the integration branch was created from
  that exact commit.
- [x] 2026-07-25: PR #11 candidate merged locally into the integration branch only;
  its upstream PR and Issue remain untouched.
- [x] 2026-07-25: PR #12 visual candidate audited. Reusable visual components and
  navigation were separated from its mock data/runtime.
- [x] 2026-07-25: RenderArtifact domain, repository, migration and application tests
  were added for exact input signatures, private provider trace, cache hits,
  degraded fallback links and pixel-only share eligibility.
- [x] Finish adapting the approved first-level pixel UI to real Item/Look APIs.
- [x] Add collage generation through the existing object store.
- [x] Add private try-on and image-generation provider adapters with bounded polling,
  timeouts, secret protection and honest fallback.
- [x] Wire API, task dispatch and worker execution.
- [x] Generate the TypeScript contract and connect Look list/detail presentation.
- [x] Remove the unused simulated-share modal and relabel the local-only profile photo
  preview so it cannot be mistaken for a persisted personal try-on input.
- [x] Use only a successful share-safe `pixel_cover` artifact as the Look-card pixel
  cover; otherwise retain the real Look image or honest pending placeholder.
- [x] Ran real 390x844 journeys for seeded Look browsing, personal full-body upload,
  explicit confirmation, real hosted try-on, deletion of the original full-body
  photo while retaining the generated result, real AI plan save, immediate collage,
  and independently completed pixel cover.
- [x] Stabilized dependent render signatures so a collage changing from queued to
  succeeded does not create a duplicate pixel job; the last successful pixel remains
  visible while an explicit refresh is pending.
- [x] Made curated wardrobe bootstrap idempotent across session refreshes so reopening
  the H5 does not mutate Look versions or enqueue duplicate renders.
- [x] Removed the cross-kind preview fallback that could display a real collage under
  the “真人试穿” or “像素封面” tabs before those artifacts existed. The UI now shows
  an explicit upload/generate state, preserves an older successful artifact of the
  same kind during refresh, and uses a collage only when the artifact records an
  explicit fallback id.
- [x] Finish the full product CI suite and independent final reviews.
- [ ] Push the tested integration branch without closing or merging upstream PRs.

## Reuse audit

| Capability | Candidates audited | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| First-level pixel UI | PR #12; current H5; `_ref/StyleCapture-main` | Adapt PR #12 visual components onto current real screens | Preserves the approved visual result without importing mock state | User-owned project code |
| Item/Look data | PR #12 mock API; current generated API client | Directly reuse current API and generated contracts | Prevents a second product truth and frontend/backend drift | This repo; `openapi-typescript` MIT |
| Artifact persistence | New file store; current `LocalObjectStore`; Look SQLAlchemy repository | Extend/reuse the existing content-addressed and async repository patterns | Avoids duplicate media validation, paths, private streaming rules and idempotency mechanics | This repo; Pillow HPND |
| Immediate collage | Browser canvas; ImageMagick; Pillow | Thin Pillow renderer in the media worker | Pillow is already installed and tested; output is deterministic and portable | Pillow HPND |
| Async execution | New queue; current Capture Celery/Redis pipeline | Reuse task dispatch, worker lifecycle and retry conventions | One queue/state mechanism avoids task drift | This repo; Celery BSD-3-Clause |
| Pixel generation | Browser procedural avatar; new diffusion pipeline; `_ref/StyleCapture-main` provider router | Adapt the existing provider-router contract to the LiteLLM `image_generation` capability | Keeps the approved character identity without shipping a local diffusion model | User-owned reference; LiteLLM MIT |
| Try-on | Local FastFit/FASHN; hosted try-on API | Stable provider port with a hosted default; local heavy adapters remain optional | Full effect without a GPU deployment prerequisite | Hosted API; optional upstream licenses recorded before use |
| API DTOs | Handwritten H5 types; backend OpenAPI generation | Direct reuse of the generator | Duplicate DTOs are a merge blocker | `openapi-typescript` MIT |

Adding an implementation without updating this audit is a P1 merge blocker. Do not
copy entire `_ref` projects, introduce unused heavy dependencies, or define the same
contract independently in the browser, API and worker.

## Verification

- [x] Render core lint:
  `uv run --project services/backend ruff check services/backend/src/stylecapture_backend/features/render services/backend/tests/render services/backend/migrations/versions/20260725_0009_render_artifacts.py`
- [x] Render core typing:
  `uv run mypy services/backend/src/stylecapture_backend/features/render services/backend/tests/render`
- [x] Render domain/application/repository tests:
  `uv run pytest services/backend/tests/render -q`
- [x] Adjacent Look + Render tests:
  `uv run pytest services/backend/tests/look/test_domain.py services/backend/tests/look/test_look_application.py services/backend/tests/look/test_repository.py services/backend/tests/render -q`
- [x] Architecture boundary test:
  `uv run pytest services/backend/tests/architecture/test_boundaries.py -q`
- [x] Backend domain/repository/application/provider/API/worker tests pass:
  `247 passed`.
- [x] Contract generation is stable and H5 typecheck/tests/build pass:
  `48` H5 tests and `4` matching-skill tests.
- [x] An uncached completed Look produces a real collage from its Item display assets.
- [x] At least one real hosted generation call succeeds when its server-side credential
  is configured; missing credentials produce an explicit retryable/unavailable state,
  not a fixed image.
- [x] Saving one recommended plan persists one `ai_generated` Look, returns immediately,
  and independently queues collage plus pixel cover; the first completed artifact
  updates only that Look without waiting for sibling plans or renders.
- [x] “试穿这套” captures or uploads a full-body reference with explicit confirmation,
  sends it only to the private try-on pipeline, and labels the result as personal only
  when that exact reference is recorded in the RenderArtifact signature.
- [x] Try-on timeout, unsupported category and provider failure visibly fall back to the
  collage without changing the try-on truth.
- [x] Repeating the exact successful request hits the recorded successful artifact;
  changed Item/Look/reference inputs do not.
- [x] Share output contains only the pixel artifact and approved copy, never a user
  reference photo, source frame, object key or signed provider URL.
- [x] A real 390x844 journey covers Look browsing, pending/success, opening
  the accurate real Look and returning to source.
- [x] A clean new-user session is operated end to end as a person would: enter Feed,
  pause, lasso, save Item and whole Look, observe background processing, browse Item
  and Look wardrobes, open analysis/recommendation entry points, request every render
  kind, recover from provider failure, share only the safe pixel result, and return to
  the exact source frame. Record screenshots/trace and inspect the corresponding API,
  queue, database and object-store state after every durable transition.
- [x] Run bounded concurrent save/list/detail/render/status/image traffic and inspect
  browser responsiveness, API latency/error rate, queue depth/retry behavior,
  database integrity/connection use and object-store hashes. Fix data races,
  idempotency drift, stale UI, duplicate work and resource regressions before signoff.
- [x] Senior product, architecture, security, code and visual reviews independently
  assess the experience from evaluator, first-time user and failure-recovery
  perspectives. P0/P1 findings are fixed on this branch before Issue #6 is considered.
- [x] CPU, memory, disk and Docker use stay within the lightweight guardrails; no local
  diffusion or try-on weights are loaded by default.
