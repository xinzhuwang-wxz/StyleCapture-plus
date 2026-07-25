# Feed Selection and Lightweight Ingest ExecPlan

> **For agentic workers:** implement this living plan one vertical slice at a time.
> Use behavior-first tests and update `Progress`, discoveries, decisions, and evidence
> before every meaningful pause.

**Goal:** Let a mobile user browse a real Douyin-style Feed, pause a video, draw one
or more colorful garment selections, manipulate the lifted visual subject directly,
and swipe right to durably save real asynchronous wardrobe jobs without waiting for
AI inference or requiring a GPU server.

**Architecture:** Reuse the existing Video Branch Feed mechanics and StyleCapture
wardrobe shell inside one React application. The browser owns responsive frame
capture, lasso feedback, approximate lift compositing, and swipe confirmation. The
FastAPI capture module owns the idempotent save intent; a bounded media worker performs
FFmpeg extraction and promptable segmentation behind provider ports, retaining the
coarse user selection whenever refinement is unavailable.

**Tech stack:** React 18, TypeScript, Vite, TanStack Query, Pointer Events, Canvas/SVG,
FastAPI, Pydantic, SQLAlchemy, PostgreSQL/pgvector, Celery/Redis, FFmpeg, MobileSAM
ONNX as the default refinement candidate, Playwright, Vitest, pytest, Docker Compose.

## Global Constraints

- The synchronous pause/lasso/lift/swipe path must not call a model.
- Right-swipe persists before asynchronous extraction, segmentation, or tagging.
- Runtime mocks, stubs, fixed AI results, and `curated_seed` presented as model output
  are forbidden.
- Provider/model identifiers and credentials remain in server infrastructure adapters.
- The default laptop and server path is CPU core plus hosted intelligence; CUDA images
  remain outside the default Compose profile.
- A failed refinement preserves the real frame and coarse user lasso; it must not
  silently invent a clean cutout.
- The feed and wardrobe share one session, API, asset model, task model, and navigation
  shell.
- New files stay feature-local; generic utilities require at least two real consumers.

---

## Purpose / Big Picture

The judge opens StyleCapture on a phone-sized viewport and immediately gets a browsable,
full-height video Feed. Pausing a video reveals the save affordance. Drawing one closed
loop produces a colorful trail and a small visual lift; additional loops may be drawn
without leaving the frame. After 700 ms without a new loop, the selected pixels become
one directly draggable subject. A left swipe dismisses it and writes nothing. A right
swipe returns to playback immediately, shows a quiet saved acknowledgement, and creates
one idempotent capture batch whose items later appear in the wardrobe as processing,
partial, ready, or retryable.

The behavior remains usable with every AI provider unavailable. Refinement improves
the stored mask asynchronously but is not the source of the user's save decision.

## Progress

- [x] 2026-07-25: Issue #1 baseline merged and Issue #2 branch created.
- [x] 2026-07-25: Reuse surfaces in `_ref/video-branch-main` audited.
- [x] 2026-07-25: Lightweight-first provider topology accepted in ADR-0004.
- [x] 2026-07-25: Public Feed corpus sources and fixed regression buckets researched.
- [x] 2026-07-25: Defined Feed frame/selection contracts, stable API validation,
  idempotent single-job submission, PostgreSQL round-trip, and generated TypeScript
  contracts through red-green tests.
- [x] 2026-07-25: Added a reuse-audited corpus verifier for minimum size, fixed
  regression coverage, category balance, item-level rights evidence, `curated_seed`
  provenance, unique identity, path containment, SHA-256, and FFprobe playability.
- [ ] Add provenance-recorded Feed corpus manifest and at least 30 local review clips.
- [ ] Integrate Feed browsing, pause, multi-lasso, lifted subject, and direct swipe.
- [ ] Connect right-swipe to the real upload/capture/job API with idempotent batching.
- [ ] Add FFmpeg extraction and promptable segmentation provider/fallback behavior.
- [ ] Generate OpenAPI client types and complete automated, real-user, visual, resource,
  architecture, security, and trace evidence.
- [ ] Merge the reviewed Issue #2 pull request and immediately advance the Goal.

## Surprises & Discoveries

- 2026-07-25: The reusable Video Branch implementation already contains scroll snap,
  active-video control, letterbox-correct coordinate conversion, same-origin canvas
  frame capture, and SVG lasso mechanics. Its branch-response card and client-side API
  key paths are intentionally not reusable.
- 2026-07-25: The existing capture domain already accepts `source_kind=feed`, but its
  HTTP contract accepts one prepared image and has no frame timestamp, normalized
  selection paths, source video identity, or multi-selection batch invariant.
- 2026-07-25: A model is unnecessary for the visual lift. A composited frame clipped by
  the user's own lasso gives immediate honest feedback; the durable refined mask may
  arrive later.
- 2026-07-25: The current 4 vCPU / 8 GiB host is viable for the core only when Feed and
  generated media are delivered by COS/CDN rather than its 5 Mbps public link.
- 2026-07-25: A JSONB `source_metadata` envelope can persist the versionable Feed
  selection context without leaking provider DTOs into the capture domain or forcing a
  premature multi-table component model. Integration evidence: the exact two-selection
  value survives PostgreSQL migration and round-trip.
- 2026-07-25: Hourly audit found an unrelated `video-branch` PostgreSQL container still
  running from the reusable reference project. It was stopped without deleting its
  volume; the current StyleCapture Compose project remains healthy. Memory compression
  is high, so remaining corpus and test work stays sequential and bounded.
- 2026-07-25: Full-suite verification caught that removing the JSONB migration default
  broke legacy raw-SQL capture inserts even though ORM-based Feed tests passed. A
  follow-up migration and matching model `server_default` restore backward
  compatibility. Fresh evidence: 82 backend tests, four H5 tests, typecheck, production
  build, healthy Compose, and the existing 390×844 upload/delete/reload Playwright path
  with a 5.9 MiB trace all pass.
- 2026-07-25: The first concrete 30-item Pexels candidate set is a discovery pool, not
  an acceptable corpus: it contains too few videos and does not satisfy the locked
  8/8/4/4/4/2 category distribution. Its non-canonical `accessories`, `boutique`, and
  `mannequin` labels would also fail the Pydantic contract. No candidate was downloaded
  or relabeled to manufacture coverage; a source-verified replacement pass is required.

## Decision Log

- 2026-07-25 — Use one integrated React application with Feed and wardrobe routes.
  Rationale: shared state and transitions must feel like one product, not two embedded
  demos. Affected contracts: H5 app shell, navigation, session.
- 2026-07-25 — Treat every closed lasso as a separate selection but submit the settled
  frame as one idempotent batch. Rationale: multiple liked garments should require one
  confirmation while preserving per-item boundaries. Affected contracts: Feed
  selection DTO, capture application, worker task.
- 2026-07-25 — Settle after 700 ms without a new pointer-down; do not lift the final
  group after every loop. Rationale: supports consecutive selections without stuttering
  while keeping the action legible. Affected contracts: Feed interaction state machine.
- 2026-07-25 — Default refinement is MobileSAM/ONNX on one still frame with a durable
  coarse-lasso fallback; SAM2.1 is a quality tier. Rationale: ADR-0004 makes GPU
  optional and keeps the interaction independent of inference. Affected contracts:
  `PromptableSegmentationPort`, worker result metadata, deployment profiles.
- 2026-07-25 — Curated demo annotations are stored as `curated_seed` provenance, never
  accepted as runtime provider evidence. Rationale: known corpus preparation must not
  be confused with product AI. Affected contracts: corpus manifest and trace review.

## Context and Orientation

`Capture` is a durable user save intent and source image. `ProcessingJob` tracks
asynchronous work. `Item` is the unique wardrobe fact created from a reliable
selection. A Feed frame may produce a `SelectionBatch` containing several normalized
lasso paths. Each path can produce one Item task, but retries of the batch may not
create duplicates.

Existing production code:

- `apps/h5/src/app/App.tsx` owns the current wardrobe-only shell and upload flow.
- `apps/h5/src/api/client.ts` owns the generated-contract-backed product API client.
- `services/backend/src/stylecapture_backend/features/capture/` contains capture domain,
  application, HTTP, repositories, and worker processing.
- `services/backend/src/stylecapture_backend/features/wardrobe/` owns Item truth.
- `docker-compose.yml` defines the portable local core.

Approved reuse:

- `_ref/video-branch-main/apps/h5/src/components/Feed.tsx`: scroll-snap Feed and active
  index mechanics.
- `_ref/video-branch-main/apps/h5/src/components/VideoScreen.tsx`: active playback,
  pause reset, video-content coordinate conversion, canvas capture, and lasso mechanics.
- Existing StyleCapture `apps/h5/src/app/styles.css` and pixel character assets:
  wardrobe visual identity.

Rejected reuse:

- `BranchCard`, `EvidencePlayer`, question/answer branch state, and client-side model
  calls do not match the product contract.
- The old global `VideoScreen.tsx` state bag must be decomposed into Feed selection
  state, viewport mapping, and presentation components before extension.

### Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Capture/job/idempotency | Issue #1 capture module; `wardrowbe` | Adapt existing capture module | It already owns signed upload, session scope, durable jobs, retry, provider ports, and tests; Feed adds typed source metadata only | This repo baseline `a8c7f31`; `wardrowbe@c63ced9`, MIT |
| Feed browsing and viewport math | `_ref/video-branch-main` Feed/VideoScreen | Adapt selected functions and behavior | Scroll snap, active playback, letterbox coordinate conversion, canvas frame capture, and lasso are proven; branch-response UI/data model conflicts with this product | Internal user-owned snapshot dated 2026-07-23; no external license file |
| Wardrobe visual identity | `_ref/StyleCapture-main` | Adapt CSS/assets/page semantics | Preserves the approved purple-pixel identity without importing the global script/state architecture | Internal user-owned snapshot dated 2026-05-24; no external license file |
| API contracts | Handwritten duplicate TypeScript types; OpenAPI generator | Reuse generated OpenAPI client types | One backend contract source prevents H5 drift | `openapi-typescript@7.13.0`, MIT |
| Frame extraction | Browser seek logic; custom decoder; FFmpeg | Reuse FFmpeg | Mature timestamp-aware decoding avoids a custom media stack | Local FFmpeg 8.0.1; LGPL/GPL build terms retained with deployment |
| Corpus manifest validation | Handwritten schema; JSON Schema dependency; existing Pydantic + FFprobe | Reuse Pydantic and FFprobe behind a thin repository script | Pydantic already defines product contracts; FFprobe proves real playability. Only cross-asset coverage, provenance, and hash rules are product-specific | `pydantic@2.12.5`, MIT; local FFmpeg/FFprobe 8.0.1 |
| Corpus download and review transcoding | Custom HTTP downloader/decoder; curl; HTTPX; FFmpeg | Reuse FFmpeg's HTTPS demuxer and transcoder behind a sequential, atomic thin wrapper | Avoids a second decoder and full-size UHD staging files; one asset is bounded and published only after FFprobe succeeds, so retries resume without laptop saturation | local FFmpeg 8.0.1, LGPL/GPL build terms retained with deployment |
| Still-frame segmentation | Coarse polygon; MobileSAM; SAM2.1; Grounded-SAM2 | Coarse polygon truth + adapted MobileSAM default; heavier candidates quality-only | Keeps core CPU-compatible and preserves save intent when inference fails | `MobileSAM@f706ad9`, Apache-2.0; `sam2@2b90b9f`, Apache-2.0; `Grounded-SAM-2@b7a9c29`, Apache-2.0 |
| Gesture animation | Handwritten animation engine; Motion; SVG/Canvas | Reuse Motion and browser primitives | Existing dependency supplies drag/spring behavior; Canvas/SVG supplies exact lasso visuals without a 3D engine | `motion@12.23.24`, MIT; browser standards |

## Plan of Work

### Milestone 1: Durable Feed selection tracer

Create a feature-local Feed capture contract with normalized paths, frame timestamp,
source video reference, frame dimensions, and a batch idempotency key. Extend the
capture domain/application/repository migration so one accepted Feed frame can retain
multiple selections and dispatch exactly one batch. Add the HTTP endpoint through the
existing upload preparation flow; regenerate OpenAPI types. Prove a duplicate request
returns the original capture/job identities and a left swipe never calls it.

### Milestone 2: Provenance-recorded review Feed

Create `apps/h5/public/feed/manifest.json` and a documented ingestion script that
validates source page, creator/platform clue, usage note, SHA-256, duration, dimensions,
category buckets, fixed-regression membership, and optional `curated_seed` annotation.
Download and transcode sequentially to 480x854 H.264/AAC or smaller equivalent assets.
Reject private/paywalled sources and preserve replacement instructions. Validate at
least 30 playable entries and eight fixed difficult cases without saturating the laptop.

### Milestone 3: Integrated mobile Feed interaction

Refactor the H5 shell into Feed and wardrobe destinations without losing Issue #1.
Implement `FeedScreen`, `FeedVideo`, `useFeedSelection`, `LassoOverlay`, and
`LiftedSelection`. Reuse the audited viewport math. Test pointer cancellation,
letterboxing, multiple loops, 700 ms settle, direct horizontal drag, swipe thresholds,
resume behavior, reduced motion, and accessible non-gesture controls.

### Milestone 4: Real asynchronous ingest and lightweight refinement

On right swipe, capture the exact decoded frame, upload it through the existing signed
flow, and submit the selection batch. Show only the locally derived lifted pixels until
the server provides a refined result. Add an FFmpeg frame extractor port and
`PromptableSegmentationPort`; implement coarse polygon output as the always-available
truthful fallback and a separately enabled MobileSAM ONNX adapter. Record provider,
model/schema version, mask confidence, latency, and fallback reason without secrets.
Route reliable selections into the existing Item pipeline and preserve partial/retry.

### Milestone 5: Product-grade acceptance and merge

Run backend and H5 unit/integration suites, OpenAPI drift, architecture boundaries,
Playwright mobile journeys, and Docker core smoke. Operate the Feed as a user across
initial, pause, multi-select, lifted, dismiss, saved, processing, partial, error, retry,
and wardrobe states. Capture screenshots and a trace, compare MobileSAM and the coarse
fallback on the fixed difficult subset, inspect resource pressure, and run independent
code/security/architecture/visual reviews. Fix all P0/P1 findings in this Issue, clean
changed code, rerun affected checks, update the Issue/PR/ExecPlan, and merge only on
APPROVE + CLEAR.

## Concrete Steps

All commands run from `/Users/bamboo/Githubs/StyleCapture-plus`.

1. Baseline:

       git status --short
       docker compose -f docker-compose.yml config --quiet
       uv run ruff check services/backend
       uv run mypy services/backend/src
       uv run pytest -q
       pnpm lint
       pnpm typecheck
       pnpm test

   Expected: only recorded living-state/document changes are present; Compose parses;
   the Issue #1 suite passes.

2. Backend tracer test:

       uv run pytest services/backend/tests/capture/test_feed_selection_application.py -q

   First expected result: failure because the selection batch contract is absent.
   Passing result: a real Feed submission stores normalized paths once and reuses the
   original identities on an identical idempotency key.

3. HTTP and contract:

       uv run pytest services/backend/tests/api/test_capture_http.py -q
       pnpm contracts:generate
       git diff --exit-code apps/h5/openapi.json apps/h5/src/api/schema.d.ts

   Expected: authenticated 202 response, stable validation errors, and no generated
   contract drift after regeneration.

4. H5 interaction:

       pnpm --filter @stylecapture/h5 test
       pnpm --filter @stylecapture/h5 typecheck

   Expected: multi-lasso settle and swipe tests pass; upload/camera wardrobe tests
   remain green.

5. Feed corpus:

       python scripts/feed_corpus.py ingest \
         data/feed/sources.json \
         apps/h5/public/feed/manifest.json \
         --clip-duration 6
       python scripts/feed_corpus.py verify apps/h5/public/feed/manifest.json

   Expected: at least 30 unique valid SHA-256 entries, eight fixed regression entries,
   playable media metadata, and complete provenance.

6. Full verification:

       uv run ruff check services/backend
       uv run mypy services/backend/src
       uv run pytest -q
       pnpm lint
       pnpm typecheck
       pnpm test
       pnpm build
       docker compose -f docker-compose.yml up -d --build
       pnpm --filter @stylecapture/h5 e2e
       docker compose ps

   Expected: all checks pass, the core is healthy, and the mobile browser journey saves
   a real Feed capture and later observes its wardrobe task state.

7. Resource evidence:

       docker stats --no-stream
       df -h .
       sysctl vm.swapusage

   Expected: no unbounded duplicate workers; one media/refinement task at a time; disk
   and memory remain inside `docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md`.

## Validation and Acceptance

- Contract: normalized paths are clamped to video-content coordinates and reject
  fewer than three unique points, non-finite numbers, oversized batches, and timestamp
  outside known duration tolerance.
- Domain: one Feed frame maps to one capture batch; each stable selection key maps to
  at most one Item task; retry is idempotent.
- UI: a loop visibly follows the pointer, subsequent loops do not force an intermediate
  swipe, the group settles after 700 ms, and the actual lifted pixels move with drag.
- Interaction: left dismissal performs no write; right save resumes the same Feed
  position without waiting for server AI.
- Failure: upload, dispatch, extraction, and refinement failures retain the user's save
  intent and expose a truthful processing/partial/retry state.
- Provider: coarse lasso works with no model; MobileSAM adapter is optional; no SAM2,
  Grounded-SAM2, FashionSigLIP, try-on, or image-generation weight is loaded by the
  Issue #2 core.
- Corpus: 30 provenance-recorded samples and eight fixed regression samples are locally
  playable. Manual annotations are visibly marked `curated_seed`.
- Compatibility: camera/upload flows and wardrobe correction/delete/retry behavior from
  Issue #1 remain unchanged.
- Security: no source media path crosses users; URLs are bounded/signed or same-origin;
  browser bundles, logs, screenshots, and traces contain no provider credential.
- Visual: captured mobile states score at least 90 under the project visual gate and
  retain both the Douyin-style Feed and StyleCapture wardrobe identity.

## Idempotence and Recovery

The browser generates one idempotency key when a settled selection enters the save
state and retains it across upload or network retries. The server never derives
idempotency from mutable provider output. FFmpeg extraction writes to a content-hash
key. Refinement writes a versioned derivative and never overwrites the original frame
or normalized lasso.

If the user navigates away after right swipe, the accepted job continues and reappears
from server truth. If only some selections refine successfully, successful Items are
kept and failed selections remain partial/retryable. Reprocessing may replace generated
derivatives only when the provider/schema version is explicit; it cannot replace user
corrections or ownership.

Corpus downloads use a staging file, verify media and SHA-256, then rename atomically.
An interrupted download is safe to retry. Docker cleanup is limited to project-owned
containers and caches; no global prune is permitted.

## Outcomes & Retrospective

Not yet delivered. On completion, record:

- merged commit and pull request;
- automated test, OpenAPI, Docker, and resource summaries;
- real mobile trace and screenshot paths;
- fixed-subset segmentation comparison;
- review verdicts and resolved findings;
- remaining non-blocking limitations that do not violate Issue #2 acceptance.
