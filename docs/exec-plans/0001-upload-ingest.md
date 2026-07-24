# Upload / Camera to Digital Wardrobe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended when explicitly authorized) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A mobile user can upload or photograph one garment, mark it as owned or inspiration, leave the screen while processing continues, and later see the real image plus model-derived attributes in the StyleCapture wardrobe.

**Architecture:** Build one deployable backend codebase with two thin entrypoints: FastAPI for synchronous product APIs and Celery for asynchronous processing. Keep the `Capture` and `Item` domain pure, place provider and database details behind ports, derive TypeScript contracts from FastAPI OpenAPI, and use the existing React/Vite Feed shell plus migrated StyleCapture visual tokens for the mobile experience.

**Tech Stack:** React 18, TypeScript, Vite, TanStack Query, Motion, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 17 + pgvector, Redis 7, Celery 5, LiteLLM, Doubao vision, FashionSigLIP, Docker Compose, pytest, Vitest, Playwright.

## Global Constraints

- Runtime product intelligence must call a configured provider through LiteLLM; no mock, stub, fixed result, or Codex-generated runtime output.
- Feed corpus metadata may be manually pre-annotated only as `curated_seed`; that exception does not apply to new user uploads.
- Provider keys and concrete provider details stay server-side. Product code uses capability aliases.
- Domain modules may not import FastAPI, SQLAlchemy, Celery, LiteLLM, React, or provider DTOs.
- Source `Capture` records and original object keys are immutable from product UI.
- Model updates may not overwrite a field the user has manually corrected.
- Core Docker services must stay laptop-safe; FashionSigLIP loads only in the `ai-light` worker profile.
- All visible behavior is validated on a mobile viewport with real API and database state.
- Reused code is adapted behind current contracts; production code never imports from `_ref`.
- Commits follow the repository Lore Commit Protocol.

---

## Purpose / Big Picture

Issue #1 establishes the first real product slice and the conventions every later Issue reuses. A judge opens the H5, chooses “拍一件” or “从相册选”, selects “我的衣服” or “穿搭灵感”, confirms the image, sees a processing item in the wardrobe, and then sees the real item detail after the asynchronous job finishes. A failure remains visible and retryable without losing the original image.

The slice is complete only when the product UI, HTTP contracts, asynchronous worker, PostgreSQL state, provider boundary, Docker topology, trace evidence, and mobile screenshots agree.

## Progress

- [x] (2026-07-25 03:08 CST) Audited `video-branch-main`, `StyleCapture-main`, and `wardrowbe` reuse surfaces and licenses.
- [x] (2026-07-25 03:08 CST) Selected `issue/1-upload-ingest`; confirmed only hourly-heartbeat documentation edits pre-existed on the branch.
- [x] (2026-07-25 03:19 CST) Established the monorepo skeleton, dependency locks, architecture boundary checks, and green baseline in `a641916`.
- [x] (2026-07-25 03:42 CST) Implemented and locally verified signed upload, HEIC validation, idempotent `Capture` persistence, broker redrive, generated OpenAPI contracts, and durable PostgreSQL job state in `2986791`.
- [ ] Implement Celery processing through vision and embedding ports, guarded model updates, retry, and partial/error recovery.
- [ ] Implement StyleCapture mobile capture and wardrobe UI using only the generated client.
- [ ] Run contract, domain, worker, Compose, real-provider, mobile, visual, security, and architecture verification.
- [ ] Update this plan’s outcomes, GitHub Issue/PR evidence, and merge before entering Issue #2.

## Surprises & Discoveries

- `video-branch-main` is a useful React/Vite/FastAPI/contract/trace skeleton, but its TypeScript contract is maintained by hand and its H5 stores a development API key. This slice replaces both patterns with generated OpenAPI types and server-safe authentication.
- `StyleCapture-main` contains the desired purple/pink wardrobe semantics and pixel assets, but the prototype uses global browser state and large inline-style components. Only tokens, layout semantics, copy, and assets will be migrated.
- `wardrowbe` has strong image validation, HEIC conversion, item lifecycle, manual-field guard, and async tagging patterns. Its direct multipart create route, arq runtime, user-configured provider endpoints, and broad item model are not copied.
- The repository currently has documentation only, so there is no executable baseline to preserve. The first skeleton commit must establish its own tests and reproducible setup.
- TypeScript project builds generate `*.tsbuildinfo` even with `noEmit`; it is now explicitly ignored after the first build exposed the artifact.
- A production-wired API smoke accepted the real `/Users/bamboo/Downloads/IMG_2310.HEIC`, persisted its immutable source and queued job, and placed one JSON task on Redis without requiring an AI worker or GPU.
- Pulling the Redis container image was unreliable on the current network, so the same broker contract was validated against the locally installed Redis binary. Redis remains in Compose and is not a development blocker.

## Decision Log

- **2026-07-25 — One backend package, two process entrypoints.** FastAPI and Celery share feature modules but run as separate containers. This avoids duplicated contracts while keeping transport and worker adapters thin.
- **2026-07-25 — Local signed upload adapter first.** The Product API issues an expiring HMAC-signed `PUT` URL served by the backend. The application depends on an `ObjectStore` port, so S3/OSS can replace it without changing capture contracts.
- **2026-07-25 — Capture before Item.** Confirming an upload creates an immutable `Capture` and durable `ProcessingJob`; the worker creates or updates the canonical `Item`. A worker failure never deletes the capture or original object.
- **2026-07-25 — Field envelopes protect corrections.** Model-derived attributes are stored as `{value, provenance, confidence, locked}`. Manual correction sets `provenance=user` and `locked=true`; worker merges skip locked fields.
- **2026-07-25 — FashionSigLIP is opt-in locally, mandatory in AI validation.** The `core` profile remains responsive without loading the model. The `ai-light` profile installs and runs the real embedding adapter. Missing model capability produces an explicit `partial`, never a synthetic embedding.

## Context and Orientation

### Domain vocabulary

- `Capture`: immutable record of one acquisition event and its source bytes.
- `Item`: canonical reusable garment asset in the digital wardrobe.
- `OwnershipState`: `owned` or `inspiration`; purchase transitions come in a later Issue.
- `ProcessingJob`: durable asynchronous state exposed to UI and SSE.
- `FieldEnvelope[T]`: a value with provenance, confidence, model version, and manual lock.

### Reuse map

| Source | Reuse now | Adaptation boundary |
| --- | --- | --- |
| `_ref/video-branch-main` | pnpm/uv workspace shape, Vite mobile shell, API/trace conventions, Docker database baseline | Rename packages, replace hand-written TS contract, remove browser API key, preserve Feed for Issue #2 |
| `_ref/StyleCapture-main` | purple/pink tokens, wardrobe layout, capture entry semantics, pixel character assets | Convert globals and inline styles to typed components and CSS modules/tokens |
| `_ref/third-party/wardrowbe` (`c63ced9`, MIT) | HEIC validation/resize approach, item lifecycle, async tagging and guarded update patterns | Celery instead of arq; `Capture/Item` contracts instead of third-party tables; LiteLLM capability alias instead of per-user provider URLs |

### Target file map

```text
apps/h5/
  src/app/App.tsx
  src/app/styles.css
  src/api/client.ts
  src/api/schema.d.ts
  src/features/capture/CaptureSheet.tsx
  src/features/capture/useCaptureFlow.ts
  src/features/wardrobe/WardrobeScreen.tsx
  src/features/wardrobe/ItemCard.tsx
  src/features/wardrobe/ItemDetail.tsx
  tests/capture-flow.test.tsx
  e2e/upload-to-wardrobe.spec.ts
services/backend/
  src/stylecapture_backend/main.py
  src/stylecapture_backend/worker.py
  src/stylecapture_backend/platform/{config,database,errors,trace}.py
  src/stylecapture_backend/features/capture/{domain,ports,application}.py
  src/stylecapture_backend/features/capture/infrastructure/{models,repository,object_store,providers,tasks}.py
  src/stylecapture_backend/features/capture/interfaces/{http,worker}.py
  src/stylecapture_backend/features/wardrobe/{domain,application}.py
  src/stylecapture_backend/features/wardrobe/infrastructure/{models,repository}.py
  src/stylecapture_backend/features/wardrobe/interfaces/http.py
  migrations/
  tests/
config/litellm.yaml
scripts/check_boundaries.py
scripts/export_openapi.py
docker-compose.yml
```

## Plan of Work

### Milestone 1: Reproducible skeleton and pure contracts

**Result:** A new checkout installs with pnpm and uv, imports are statically checked, and domain tests run without database, network, or framework dependencies.

**Files:**

- Create root `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `.env.example`, `.gitignore`.
- Create `apps/h5/package.json`, TypeScript/Vite/Vitest configuration, `index.html`, and minimal `src/main.tsx`.
- Create `services/backend/pyproject.toml` and package entrypoints.
- Create `scripts/check_boundaries.py`.
- Test `services/backend/tests/architecture/test_boundaries.py`.

**Interfaces:**

- `Capture.create(user_id: UUID, object_key: str, ownership: OwnershipState, source: CaptureSource) -> Capture`
- `ProcessingJob.queued(capture_id: UUID) -> ProcessingJob`
- `ItemAttributes.merge_model(fields: Mapping[str, ModelField]) -> ItemAttributes`
- Boundary checker returns a nonzero exit when a pure module imports a forbidden dependency.

**TDD cycle:**

- [x] Write domain tests for legal state transitions, immutable source fields, and locked-field merge.
- [x] Run `uv run pytest services/backend/tests/domain -q`; expect import failure because the domain package does not exist.
- [x] Implement the minimal frozen dataclasses/enums/value objects.
- [x] Run the domain tests; expect all pass.
- [x] Write boundary tests with one temporary forbidden import fixture.
- [x] Run the boundary test; expect failure until `scripts/check_boundaries.py` exists.
- [x] Implement the AST import checker and run `uv run python scripts/check_boundaries.py services/backend/src`; expect `architecture boundaries: ok`.
- [x] Run `pnpm test` and `uv run pytest -q`; expect a green skeleton.
- [x] Commit with Lore trailers and record the commit in `Progress`.

### Milestone 2: Durable upload and job API

**Result:** Real JPEG/PNG/WebP/HEIC bytes are validated, stored under a signed object key, and confirmed as an idempotent Capture plus queued job in PostgreSQL.

**Files:**

- Create Alembic configuration and initial migration for `captures`, `processing_jobs`, `items`, and `pgvector`.
- Create platform config/database/error modules.
- Create capture ports, application service, SQLAlchemy models/repository, and local signed object store.
- Create capture and job HTTP routers.
- Create contract/API tests and object-store tests.

**Interfaces:**

```python
class ObjectStore(Protocol):
    def prepare_upload(self, request: UploadRequest) -> PreparedUpload: ...
    def accept_upload(self, token: str, body: BinaryIO, content_type: str) -> StoredObject: ...
    def open(self, object_key: str) -> BinaryIO: ...

class CaptureRepository(Protocol):
    def find_by_idempotency(self, user_id: UUID, key: str) -> CaptureSubmission | None: ...
    def save_submission(self, capture: Capture, job: ProcessingJob) -> CaptureSubmission: ...

class JobDispatcher(Protocol):
    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None: ...
```

**HTTP contract:**

- `POST /v1/uploads/prepare` validates name, MIME, byte limit, and SHA-256; returns `upload_url`, `object_key`, `expires_at`.
- `PUT /v1/uploads/{token}` validates signature, expiry, content length, MIME, decoded image, and hash; returns the stored object key.
- `POST /v1/captures` requires `Idempotency-Key`; returns HTTP 202 with `capture_id`, `job_id`, and `status_url`.
- `GET /v1/jobs/{job_id}` returns `queued|processing|partial|ready|error`.
- `GET /v1/jobs/{job_id}/events` streams versioned SSE state changes and ends on a terminal state.
- Stable errors use `{"error":{"code": str, "message": str, "request_id": str, "details": object}}`.

**TDD cycle:**

- [x] Write failing API tests for invalid type, excessive bytes, expired token, hash mismatch, repeated idempotency key, unknown job, and SSE terminal state.
- [x] Run targeted tests and confirm failures are caused by missing routes.
- [x] Implement the object store and application service without importing transport or ORM types into the domain.
- [x] Implement SQLAlchemy repositories and migration.
- [x] Implement thin HTTP adapters and error mapping.
- [x] Run targeted tests, then `uv run pytest services/backend/tests -q`.
- [x] Export OpenAPI and generate `apps/h5/src/api/schema.d.ts`; fail CI if regeneration changes tracked output.
- [x] Commit with Lore trailers and update `Progress`.

### Milestone 3: Real asynchronous understanding and guarded persistence

**Result:** Celery processes a real Capture, calls Doubao vision through LiteLLM, calls FashionSigLIP through its adapter, stores trace/model metadata and a pgvector embedding, and preserves manual corrections.

**Files:**

- Create provider ports and adapters.
- Create capture processing application service and Celery adapter.
- Create `config/litellm.yaml`.
- Create worker, provider-contract, retry, guarded-update, and partial-state tests.

**Interfaces:**

```python
class VisionTagger(Protocol):
    async def describe(self, image: ImagePayload) -> VisionResult: ...

class ImageEmbedder(Protocol):
    def embed(self, image: ImagePayload) -> EmbeddingResult: ...

async def process_capture(
    capture_id: UUID,
    job_id: UUID,
    captures: CaptureRepository,
    wardrobe: WardrobeRepository,
    vision: VisionTagger,
    embedder: ImageEmbedder,
    events: JobEventSink,
) -> ProcessingOutcome: ...
```

The vision result schema includes category, subcategory, colors, material, pattern, silhouette, fit, style, season, occasion, natural-language description, field confidence, and model metadata. Invalid or incomplete model JSON is a typed provider error; it is never replaced by fixed tags.

**TDD cycle:**

- [ ] Write tests using fakes only through `VisionTagger` and `ImageEmbedder` ports.
- [ ] Verify red for success, vision retry, embedding-only failure → `partial`, final provider failure → `error`, user lock preservation, and retry from retained Capture.
- [ ] Implement processing application logic and guarded field merge.
- [ ] Implement Celery dispatch/retry and terminal event emission.
- [ ] Implement LiteLLM adapter using the `vision-understanding` capability alias and structured response validation.
- [ ] Implement lazy FashionSigLIP adapter using `Marqo/marqo-fashionSigLIP`; no model loads during import or `core` profile startup.
- [ ] Run worker and contract tests.
- [ ] If provider credentials exist, run the opt-in real-provider smoke with `/Users/bamboo/Downloads/IMG_2310.HEIC`; record model IDs, latency, output schema, and trace without secret values.
- [ ] Run the FashionSigLIP smoke only if resource guardrails remain green; otherwise run it in the `ai-light` container with limited CPU/memory.
- [ ] Commit with Lore trailers and update `Progress`.

### Milestone 4: StyleCapture mobile capture and wardrobe

**Result:** The mobile H5 performs the whole flow through generated API contracts and displays processing, partial, ready, error, cancellation, and retry states in the StyleCapture visual language.

**Files:**

- Create typed API client from generated OpenAPI types.
- Create capture sheet/hook and wardrobe/item components.
- Migrate required StyleCapture token values and selected pixel assets.
- Create Vitest component tests and Playwright mobile E2E.

**Interaction contract:**

- “拍一件” opens `accept=image/*` with `capture=environment`; “从相册选” opens without capture.
- Before upload, the user selects exactly one ownership state.
- Client validates type and size before requesting an upload.
- Closing the sheet after 202 does not cancel the durable job.
- A processing tile appears immediately; terminal updates arrive from SSE with polling fallback.
- Partial/error tiles retain the original image and expose retry; ready tile opens real detail.
- No concrete provider name, secret, internal job payload, or synthetic result appears in UI.

**TDD cycle:**

- [ ] Write component tests for camera attributes, ownership requirement, client rejection, 202 transition, background continuation, partial/error retry, and ready detail.
- [ ] Confirm tests fail against the minimal shell.
- [ ] Implement the flow with TanStack Query and a feature-local state machine.
- [ ] Migrate wardrobe tokens/layout and pixel asset use; do not copy global state or large inline-style files.
- [ ] Run `pnpm --filter @stylecapture/h5 test`.
- [ ] Run the real backend and execute Playwright at 390×844 for upload, processing, ready, error, and retry paths.
- [ ] Commit with Lore trailers and update `Progress`.

### Milestone 5: Compose, evidence, review, and merge

**Result:** One Compose stack proves the slice from browser to database/worker and produces reviewable evidence.

**Files:**

- Create/complete `docker-compose.yml`, backend/H5 Dockerfiles, health checks, resource limits, and persistent volumes.
- Create `docs/api/garment-ingest.md`, `docs/evidence/issue-1/README.md`, screenshots, trace export, and third-party notice.
- Update GitHub Issue #1 and PR.

**TDD and verification cycle:**

- [ ] Start `docker compose up --build -d postgres redis api worker h5`; expect all health checks green without heavy local model load.
- [ ] Start the `ai-light` worker only for embedding validation under documented resource limits.
- [ ] Run migrations twice; expect idempotent success.
- [ ] Run API example calls using both Python and cURL from `docs/api/garment-ingest.md`.
- [ ] Run all Python/TypeScript tests, lint, typecheck, boundary check, generated-contract check, and Playwright.
- [ ] Personally operate the mobile path and save screenshots for empty, selecting, processing, ready/detail, partial/error, and retry recovery.
- [ ] Run visual verdict; fix every P0/P1 and repeat until score is at least 90.
- [ ] Review security, secrets, privacy, architecture, API/worker/UI state alignment, duplicate/dead code, and Docker resource usage.
- [ ] Verify `rg` finds no runtime mock/stub/fixed result, browser key, concrete provider call outside adapters, or imports from `_ref`.
- [ ] Push branch, open PR, attach exact evidence, address review findings, merge, close Issue #1, and immediately select Issue #2.

## Concrete Steps

All commands run from `/Users/bamboo/Githubs/StyleCapture-plus`.

```bash
uv sync --all-packages
pnpm install --frozen-lockfile
uv run pytest -q
pnpm test
uv run python scripts/check_boundaries.py services/backend/src
docker compose config --quiet
```

Expected at each checkpoint: exit code 0, no warning that changes behavior, no skipped required contract/domain/UI test, and no dependency on `_ref`.

For the real path:

```bash
docker compose up --build -d postgres redis api worker h5
uv run alembic -c services/backend/alembic.ini upgrade head
pnpm --filter @stylecapture/h5 exec playwright test e2e/upload-to-wardrobe.spec.ts
```

Expected: a 202 Capture submission, observed job state progression, a persisted Item, and a wardrobe detail whose source image hash matches the uploaded fixture.

## Validation and Acceptance

- API: stable errors, presigned upload, 202 job, idempotency, GET status, SSE, retry.
- Domain: immutable Capture, legal states, ownership distinction, guarded manual fields.
- Persistence: PostgreSQL migration, pgvector length and normalization, model metadata, original object key.
- Worker: retries, partial success, terminal failure, capture preservation, no synthetic fallback.
- Provider: real LiteLLM/Doubao structured output and real FashionSigLIP smoke when configured.
- UI: upload/camera, ownership, client validation, background processing, wardrobe states/detail.
- E2E: real Compose services and database, no route interception or fixture API responses.
- Visual: 390×844 screenshots, score ≥90, no clipping, unreadable copy, dead controls, or jarring transition.
- Security/privacy: no keys or provider internals in client/log/evidence; upload token expiry and size/hash validation.
- Architecture: no forbidden imports, no generic dumping module, and generated contracts are current.

## Idempotence and Recovery

- A repeated `POST /v1/captures` with the same user and idempotency key returns the original Capture/job.
- Upload token acceptance is single-object and hash-bound; replay after successful storage returns the same object metadata rather than duplicating bytes.
- Celery tasks are safe to retry because the Capture is immutable and Item upsert is keyed by Capture.
- A failed vision call leaves the Capture and original image available for retry.
- An embedding failure after valid tags produces `partial`; retry fills the embedding without overwriting locked fields.
- Compose volumes hold PostgreSQL, Redis, and uploaded originals across container restart.
- Rollback removes only code/migration changes; it never deletes user source bytes as part of an application retry.

## Outcomes & Retrospective

Not yet delivered. Replace this paragraph with exact commits, test counts, provider evidence, screenshot paths, visual verdict, known non-blocking limitations, and lessons before Issue #1 is closed.
