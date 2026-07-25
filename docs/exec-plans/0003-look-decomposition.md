# Look Decomposition and Dual Wardrobe ExecPlan

> **For agentic workers:** implement this living plan as one vertical slice. Keep
> `Progress`, discoveries, reuse evidence, and verification current. Do not defer a
> known acceptance gap to a new Issue unless it has independent product value.

**Goal:** Let a user explicitly save a whole outfit from the Feed, see a real pending
Look in the StyleCapture wardrobe immediately, and later inspect the reliably
decomposed reusable Items plus AI-extracted outfit relationships without leaving fake
or duplicated assets behind.

**Architecture:** `Item` remains the only garment fact. A feature-local `look` module
owns `Look`, `LookComponent`, and append-only `PreferenceSignal` relationships. The
synchronous save path persists the Capture and an idempotent pending Look before the
worker runs. The worker uses hosted Doubao visual grounding through LiteLLM, the
existing promptable-segmentation seam and garment tagger, then links only reliable
Items. Uncertain components remain explicit pending evidence. The H5 exposes
“穿搭 / 单品” wardrobe views backed by generated OpenAPI contracts.

**Tech stack:** React 18, TypeScript, TanStack Query, FastAPI, Pydantic, SQLAlchemy,
PostgreSQL/pgvector, Celery/Redis, LiteLLM, Doubao vision/embedding, optional
SAM 2.1 Hiera Tiny refinement, Playwright, Vitest, pytest, Docker Compose.

## Global Constraints

- The Feed must receive an explicit `item_selections` or `whole_outfit` intent; area
  heuristics may not guess what the user meant.
- Right-swipe persists a pending Look before returning success and before model work.
- One whole-outfit intent contains exactly one lasso. Several independently selected
  garments remain an Item batch.
- `Look` stores relationships and analysis only; it never copies Item facts.
- A ready component must reference a real Item. An occluded or unreliable component
  remains pending/error and may not manufacture an Item.
- The default path is CPU core plus hosted intelligence. Local GPU inference and
  deployment are optional quality/deployment work and cannot block this Issue.
- Every model call uses a server-side LiteLLM capability alias. Provider identifiers,
  credentials, fixed results, hidden mocks, and curated labels presented as AI output
  are forbidden.
- Pixel art is a later render artifact. Until a real pixel cover exists, Look cards use
  a persisted selection cutout and an honest processing state.
- The original frame/lasso is source evidence, not the normal wardrobe cover. Item and
  Look cards use persisted transparent cutouts produced by the segmentation/rendering
  pipeline, while detail pages retain a separate route back to the original frame and
  video timestamp.
- API DTOs originate from backend OpenAPI and are generated into TypeScript.
- Reuse existing contracts and adapters before adding code. Duplicate contracts or
  algorithms are a P1 merge blocker.

## Progress

- [x] 2026-07-25: Issue #2 merged and the real Feed-to-Item slice verified.
- [x] 2026-07-25: Repo, `_ref`, provider, domain, API, worker, and H5 reuse surfaces
  audited; no GPU or deployment blocker found.
- [x] 2026-07-25: Hosted Ark visual-grounding response format and LiteLLM path verified
  against official documentation.
- [x] 2026-07-25: Product contract fixed: explicit whole-outfit intent, immediate real
  Look placeholder, optional non-blocking like reason, dual wardrobe views.
- [x] 2026-07-25: Added reviewed Look domain invariants, persistence migration,
  user-scoped repository, typed failure boundaries, and 142-test backend regression.
- [x] 2026-07-25: Pending Looks and append-only PreferenceSignals are persisted
  idempotently before worker dispatch; independent code review is APPROVE.
- [x] 2026-07-25: Persisted Feed selection transparent cutouts as content-addressed
  `derived/items/{sha}.png` display assets through the existing object store, added
  `items.display_object_key` migration 0008, split Item `display_image_url` from
  `source_image_url`, regenerated OpenAPI/H5 types, and kept source deletion separate
  from derived wardrobe display.
- [x] 2026-07-25: Benchmarked SAM 2.1 Hiera Tiny on a real 480×854 Feed frame with a
  coat box prompt. The selected mask cleanly excluded the trousers; warm inference was
  0.306 s on Apple MPS and 0.609 s on CPU with two threads. CPU process RSS peaked at
  1,252 MiB, so it qualifies as an optional isolated refinement service without a GPU,
  not as a dependency of the API container.
- [ ] Complete hosted grounding, Look analysis, segmentation/tagging orchestration,
  retry behavior, and trace metadata.
- [ ] Generate API contracts and implement Feed intent plus Look list/detail/feedback.
- [ ] Run full automated verification and real 390×844 user flow with screenshots and
  trace, then review, merge, and synchronize Issue/Goal state.

## Current Product Truth

The current product already has a real Item wardrobe. Each reliable upload, camera
image, or Feed lasso becomes a `WardrobeItem`; the H5 can list Items, filter owned
versus inspiration, open the real source image, correct ownership/category, retry
failures, and delete source bytes.

Item tagging currently uses `LiteLLMVisionTagger` with strict schema validation and
the versioned `stylecapture-v1` taxonomy. The primary categories are:

- tops
- bottoms
- dresses
- outerwear
- shoes
- bags
- headwear
- accessories
- beauty_other

Each Item also retains subcategory, description, colors, materials, pattern,
silhouette, fit, styles, seasons, occasions, length, neckline, sleeve type, details,
field confidence, model/prompt/schema/taxonomy metadata, and hosted multimodal
embedding. These facts are model-derived through LiteLLM/Doubao, not copied from the
Feed corpus labels. User corrections are locked against later worker overwrites.

What is not yet present is the Look aggregate and its “穿搭” wardrobe view. This Issue
adds that missing half without replacing or weakening the existing Item wardrobe.
The current Feed worker already renders a transparent, tightly cropped PNG for VLM and
embedding, but only keeps it in memory; the Item image endpoint still returns the
original frame. This Issue persists that existing real output as a derived display
asset so the wardrobe no longer looks like a collection of screenshots.

The local review Feed currently contains 30 verified vertical videos (480×854,
179.2 seconds total, 5.2 MiB), including 8 fixed regression assets. Coverage is:
runway 8, street style 8, layering 4, accessory 4, shop/negative 4, and
low-light/historical 2. This is sufficient for the review experience and regression
matrix; adding more videos is not a prerequisite for the product slice.

The existing Feed manifest is source-level provenance, not garment annotation. Add a
separate versioned curated annotation manifest for the known corpus. Each annotated
moment records the video/time/frame identity, one Look grouping, component regions,
taxonomy-valid Item facts, annotation provenance, and a reason. Curated annotations
are allowed only as `curated_seed`: they support coverage, deterministic regression,
and prepared demo assets, and may never be presented as live model output. Uploads,
camera images, and selections outside a curated moment continue through the real
LiteLLM/Doubao path.

## Decisions

- Use explicit intent controls integrated into the paused Feed. Rationale: the product
  must distinguish one/multiple Items from a whole outfit before asynchronous AI.
- Store intent in versioned Feed source metadata with a legacy default of
  `item_selections`. Rationale: no duplicate database column is needed for a
  source-specific contract.
- Create an idempotent Look placeholder before dispatch. Rationale: the user sees a
  durable save immediately and retries can repair an interrupted submission.
- Model Look separately from wardrobe Item. Rationale: a Look is a relationship among
  Items and the same Item may belong to multiple Looks.
- Save like reasons as append-only PreferenceSignals. Rationale: a user preference
  must not silently mutate visual facts on any Item.
- Use Ark grounding tag parsing for spatial candidates and strict JSON for outfit
  analysis. Rationale: Ark documents normalized `<bbox>` tags for grounding and warns
  against prescribing bbox JSON.
- Use the existing coarse lasso as the truthful fallback and SAM 2.1 Hiera Tiny as an
  optional box/lasso-to-mask refinement service. Rationale: a real Feed benchmark
  showed useful garment separation at 0.609 s warm CPU inference with two threads and
  no GPU, but the PyTorch/Transformers runtime and roughly 1.25 GiB peak process memory
  should remain isolated from the API/worker containers.
- Persist segmentation/rendering output as the default Item/Look display asset and keep
  the original Capture separate. Rationale: the wardrobe should show clean garment or
  outfit assets while retaining auditable video evidence; matching a catalog product
  may enhance commerce later but may not replace the user's saved visual.
- Precompute one content-addressed, transparent normalized display image for each
  curated corpus component at its best annotated view, not for every video frame.
  Rationale: this gives the known Feed a polished and fast wardrobe presentation while
  keeping the original frame/time/region as evidence and the `curated_seed` provenance
  explicit.
- Ship a small, versioned cold-start wardrobe before deployment: a curated subset of
  Feed Items/Looks plus a few clearly sourced non-Feed assets. Mark every seeded record
  as `curated_seed`, never as user-owned or live AI output. Rationale: the evaluator can
  exercise recommendations and Look/Item browsing immediately without an empty-state
  dead end, while later user saves still follow the real ingest pipeline.
- Default the wardrobe to Looks once this slice is live, while retaining a clear
  “单品” view. Rationale: the approved product identity is a library of saved outfits
  backed by fine-grained reusable garment assets.

## Reuse Audit

| Capability | Candidates | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Item facts, confidence and user locks | Current wardrobe domain/repository | Direct reuse | Already enforces the unique garment truth and guarded merge | This repo, user-owned |
| Garment taxonomy and VLM tagging | Current taxonomy and `LiteLLMVisionTagger` | Direct reuse | Strict schema, normalization, provider metadata and tests already exist | This repo; LiteLLM MIT |
| Hosted visual grounding | Direct Ark SDK; custom HTTP; current LiteLLM transport | Adapt existing LiteLLM transport with a thin bbox-tag parser | Keeps credentials and provider selection server-side and avoids another SDK | LiteLLM MIT; Volcengine hosted API |
| Component mask refinement | Coarse lasso; MobileSAM; SAM 2.1 Hiera Tiny; Grounded-SAM2 | Coarse truth by default; optional SAM 2.1 Tiny service after real benchmark | The official 156 MB checkpoint produced a clean coat mask; warm inference was 0.306 s on MPS and 0.609 s on two-thread CPU, while isolation avoids adding the ~1.25 GiB runtime peak to core containers | `facebookresearch/sam2@2b90b9f`, Apache-2.0; official `facebook/sam2.1-hiera-tiny` |
| Clean wardrobe image | Current in-memory `PillowSelectionImageRenderer`; `wardrowbe` thumbnail/background-removal pipeline; custom canvas crop | Persist the existing renderer output through a thin derived-asset store; retain `wardrowbe` HTTP/rembg provider pattern as optional refinement | We already generate the correct transparent PNG for tagging, so persisting it avoids a second crop pipeline; optional background removal can improve edges without becoming an ingest dependency | This repo; `wardrowbe@c63ced9` MIT; Pillow HPND |
| Item display/source API split | Current `/v1/items/{id}/image` and source delete route; generated OpenAPI client; `_ref/third-party/wardrowbe@c63ced9` source/thumbnail separation | Adapt current Item route: `/image` serves display asset with source fallback, `/source` serves original evidence, DTO exposes both URLs | Reuses the authenticated private-media path and generated contracts without duplicating a frontend/backend contract or copying reference code | This repo; `wardrowbe@c63ced9` MIT; `openapi-typescript` MIT |
| Async processing and retries | New queue; current Capture/Celery worker | Direct reuse with a narrow whole-outfit processor port | One durable job/retry model already exists | This repo; Celery BSD-3-Clause |
| Look relationship model | Current Item schema; `wardrowbe` reference | New feature-local aggregate, informed by reference patterns | Product-specific invariants require a small local model; no copied Item facts | `wardrowbe@c63ced9`, MIT |
| Wardrobe Look visual system | New design; `_ref/StyleCapture-main` prototype | Adapt grid/detail semantics and existing current CSS/assets | Preserves approved visual identity without old globals/mocks | Internal user-owned reference |
| API types | Handwritten TS DTOs; current OpenAPI generation | Direct reuse of generator | Prevents frontend/backend drift | `openapi-typescript`, MIT |
| Private source images | Duplicate Look image hook; current `useSourceImage` | Adapt only after second real consumer exists | Reuses authenticated Blob lifecycle without premature generic utils | This repo |

## Domain and Persistence

Create `features/look/` with:

- `Look`: `id`, `user_id`, `capture_id`, `source_selection_key`, `source`,
  `status`, versioned relationship analysis, timestamps.
- `LookComponent`: stable `component_key`, Look reference, nullable Item reference,
  pending/processing/ready/error status, normalized evidence region, role/layer/order,
  confidence and grounding metadata.
- `PreferenceSignal`: append-only `look_saved` and `liking_reason_added` events with
  a user-scoped idempotency key.

Database invariants:

- one Look per `(capture_id, source_selection_key)`;
- one component key per Look;
- one non-null Item reference per Look, but the same Item may belong to many Looks;
- ready components require an Item; pending/error components may not claim one;
- PreferenceSignals are idempotent and append-only;
- source availability is derived from Capture evidence so a pending Look can truthfully
  express deleted/withdrawn source state before any Item exists.

## Vertical Slice

1. Extend Feed context with explicit intent and return Look identifiers from accepted
   whole-outfit submissions.
2. Add Look domain, migration, repository, application, HTTP list/detail/image/feedback
   endpoints, and user isolation.
3. Ensure pending Look plus `look_saved` signal idempotently before worker dispatch.
4. Add a narrow whole-outfit processor:
   - load the real saved frame and bound work to the lasso;
   - get hosted visual-grounding candidates through LiteLLM;
   - persist stable pending components;
   - refine reliable regions through the existing segmentation seam when available;
   - publish each real transparent cutout under a deterministic derived-asset key and
     attach it to the Item/Look while leaving the Capture source immutable;
   - reuse the garment tagger and embedder to create/update real Items;
   - link successful Items, retain uncertain components, and analyze outfit
     relationships;
   - aggregate processing/partial/ready/error state without changing identifiers on
     retry.
5. Add and validate the curated Feed annotation manifest, then generate one
   deterministic normalized component image per annotated best view. Runtime cache
   misses still use the same real renderer/provider path and never fabricate results.
6. Build the versioned cold-start wardrobe seed from a small annotated subset, keeping
   its provenance and ownership semantics distinct from real user assets.
7. Generate OpenAPI client types.
8. Add Feed intent controls and a dual “穿搭 / 单品” wardrobe. Whole-outfit right-swipe
   resumes playback immediately; the optional like reason is a quiet follow-up.
9. Add Look detail with real source frame, source video/time return, confirmed Items,
   pending components, analysis provenance, and source-unavailable state.

## Verification

Backend:

- domain invariants for intent, components, cross-Look Item reuse and append-only
  preference;
- migration/repository constraints, stable retry identities, source state and user
  isolation;
- provider parsing for valid/malformed/out-of-range/duplicate Ark grounding tags,
  LiteLLM alias use, timeouts and sanitized errors;
- worker reliable/occluded/partial/provider-failure/retry flows with no fake Item;
- API idempotency, immediate Look persistence, feedback, detail and source evidence;
- full lint, format, mypy, architecture boundary, pytest and migration checks.

Frontend:

- intent is explicit and whole-outfit submits exactly once;
- playback resumes while a real pending Look appears;
- “穿搭 / 单品” views do not hide partial assets or duplicate pending cards;
- optional like reason never blocks saving and retries independently;
- no static pixel asset masquerades as the saved Look;
- Item and Look grids load the persisted transparent cutout; the original frame is
  available only through explicit source evidence and return-to-video actions;
- source return seeks to the correct Feed video and timestamp;
- generated contract, TypeScript, unit tests and production build pass.

Real-user evidence:

- fresh Docker core with worker concurrency one;
- 390×844 mobile lasso, lift, whole-outfit right-swipe and continued Feed browsing;
- wardrobe processing → partial/ready transition using real hosted provider calls;
- Look list and detail screenshots showing real frame, components, analysis and source;
- browser console, network, worker logs and provider trace are clean;
- CPU, memory, swap, disk and Docker usage stay within local guardrails.

## GitHub Delivery

Before continuing development, committing, pushing, reviewing, or merging, fetch and
compare the current branch with `origin/main`, then inspect Issue #3, the branch PR,
reviews and CI. Open a draft PR once the first coherent tested slice exists. Address
review/CI changes promptly, merge only after the reuse audit and all evidence are
complete, then fast-forward local `main`, confirm Issue/PR/Goal consistency, and move
directly to Issue #4.
