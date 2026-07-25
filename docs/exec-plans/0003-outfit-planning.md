# Outfit Planning Skill ExecPlan (Issue #4)

> **For agentic workers:** implement this living plan one vertical slice at a time.
> Use behavior-first tests and update `Progress`, discoveries, decisions, and evidence
> before every meaningful pause. Work on branch
> `codex/issue-4-scene-outfit-matching`, keep it synced with `origin/main`, and
> follow `AGENTS.md`.

**Goal:** A mobile user enters a scene, weather, style, formality, comfort constraint,
or anchors an Item, and receives 3–4 structurally complete, explainably different
OutfitPlans recalled from their real digital wardrobe. The user can replace one slot
without losing accepted slots, persist a "complete this look" purchase list for missing
slots, and save the final plan as an `ai_generated` Look. H5, the Skill/Agent entry,
and the Playground call the same versioned Product API with the same rule version and
trace.

**Architecture:** A new `outfit` feature module in the FastAPI modular monolith with
`domain / application / infrastructure / interfaces` boundaries. Deterministic code
owns slot taxonomy, hard rules, SQL/pgvector recall (owned → collected/wanted →
commerce), diversity guarantees, state transitions, and purchase lists. The LiteLLM
`reasoning` capability alias is used only for aesthetic re-ranking and explanations of
already-valid candidate combinations, with schema-validated output that is re-checked
against the hard rules. Plan generation reuses the existing Celery job + status/SSE
plumbing from Issue #1; slot replacement is synchronous and deterministic.

**Tech stack:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL/pgvector, Celery/Redis,
LiteLLM gateway (`reasoning` alias, already configured in `config/litellm.yaml`),
React 18 + TypeScript + Vite + TanStack Query, generated OpenAPI TypeScript client,
pytest, Vitest, Playwright.

## Global Constraints

- Hard constraints, recall, state transitions, and purchase lists are never delegated
  to a model. The model re-ranks and explains; it cannot add items, resurrect
  rule-violating combinations, or invent commerce data.
- Recall priority is `owned > collected/wanted > commerce`; commerce entries only fill
  missing slots and, with no real commerce API, are explicit search demands plus jump
  links — never fabricated inventory, price, or "same item" claims.
- Runtime mocks, stubs, prompt-keyed caches, and fixed business results are forbidden.
  Test fakes live only in automated tests behind the feature's ports.
- Development may use a seeded wardrobe (see Milestone 0) inserted through real
  contracts and marked `curated_seed`; it is dev/test data, never presented as a model
  result, and the final smoke evidence must use really ingested Items.
- Provider/model identifiers and credentials stay in infrastructure adapters and
  server-side environment; domain and interface layers speak capability contracts.
- If the LLM re-rank fails validation or times out, the product returns the
  deterministic rule-ranked plans with an explicit non-generative explanation state.
  Fallbacks are visible product states, never fabricated success.
- Every generated plan records rule version, prompt/schema/model versions, latency,
  and a trace id retrievable by the Playground.
- New files stay feature-local; no generic `utils`/`helpers` dumping grounds.

## Purpose / Big Picture

The judge opens the H5, taps the outfit entry, types "周五面试" (optionally adds
weather, style, comfort, or anchors a wardrobe Item), and within one request/job cycle
sees 3–4 plan cards built from their real wardrobe images — collage first, no waiting
on any render pipeline. Each card shows every slot's real item photo, source,
ownership, role, and a written rationale, plus which constraint dimensions make this
plan different from its siblings. Tapping "换这件" on one slot shows ranked wardrobe
alternatives (wardrobe first, commerce only if the slot cannot be filled) and keeps
every other accepted slot untouched. A plan with missing slots exposes "补齐这套": a
persisted purchase list whose entries carry explicit search queries and jump links and
evolve `wanted → purchased_pending → owned`. Saving the final plan creates an
`ai_generated` Look visible in the wardrobe. The same request works through the Skill
script and the Playground shows the full workflow trace.

Plans are progressively disclosed: the client renders each structurally valid plan as
soon as it becomes available instead of waiting for every sibling. A plan remains an
OutfitPlan until the user explicitly chooses “保存这套”; only that action creates a
durable Look and starts that Look's independent presentation artifacts. One Look's
collage, pixel cover, or try-on task never gates another Look card.

## Progress

- [x] 2026-07-25: Issue #4 dependencies confirmed — #1 merged (PR #7), #2 merged
  (PR #8); no open PRs; branch `codex/issue-4-scene-outfit-matching` created from
  latest `main` (52e8aa5).
- [x] 2026-07-25: Reuse and best-practice audit completed (see below); ExecPlan
  authored.
- [x] 2026-07-25: Initialized `skills/scene-outfit-matching/` with the repository's
  requested Node CLI, progressive-disclosure references, 16-item `curated_seed`
  wardrobe with an intentional missing-shoes gap, strict output validation, bounded
  LiteLLM `reasoning` re-rank, and truthful deterministic fallback. Fourteen Node tests,
  the skill validator, all 28 existing H5 tests, TypeScript typecheck, and production
  build pass.
- [x] 2026-07-25: Added a zero-dependency temporary local QA Playground that calls
  the same `matchOutfits` function as the CLI; it is explicitly not the production H5
  design or deployment boundary. Playwright verified scene, style, and lightweight
  target-item journeys, the intentional missing-shoes completion branch, desktop
  1440px and mobile 390px layouts, and a clean browser console.
- [x] 2026-07-25: Verified the repository baseline and Skill tracer together:
  110 backend tests pass with real PostgreSQL plus FFmpeg/FFprobe, mypy checks all 65
  backend source files, Ruff and architecture-boundary checks pass, and the packaged
  `.skill` archive passes integrity validation.
- [x] Milestone 0: Seeded development wardrobe through real contracts.
- [x] Milestone 1: Pure outfit domain — slot taxonomy, hard-rule engine, diversity
  metric, deterministic scoring.
- [x] Milestone 2: Durable request/plan/purchase-list persistence, recall adapter,
  and async plan-generation job API.
- [x] Milestone 3: LiteLLM `reasoning` re-rank + explanations with schema validation,
  post-validation against rules, trace recording, and explicit deterministic fallback.
- [x] Milestone 4: H5 outfit journey — request screen, plan cards with immediate real
  collage, slot replace, purchase list, save-as-Look; regenerated OpenAPI client.
- [x] Milestone 5 implementation: the Skill entry is a thin Product API client and its
  duplicate mock/runtime rule engine was removed. Full evidence, final reviews,
  cleanup and branch publication remain the integration sign-off.
- [x] 2026-07-25: Added an idempotent judge cold start through the production
  session, Capture, Wardrobe, Look, and object-store contracts: 10 real Item records
  (5 owned, 5 inspiration) and 3 relationship-preserving Looks. Every human-authored
  field and analysis is explicitly `curated_seed`; source URLs and review state are
  retained. Mobile verification shows 10 Items and 3 Looks without an empty-state
  detour.
- [x] 2026-07-25: Added the first Product API tracer at `POST /v1/outfit-plans`.
  It reads the authenticated user's ready/partial WardrobeItems, builds four closed
  candidates with explicit missing-slot search demands, and lets LiteLLM
  `reasoning` reorder and explain only those candidates. OpenAPI and the generated
  H5 schema were regenerated.
- [x] 2026-07-25: Replaced the H5 “真实推荐待接入” placeholder with the real wardrobe
  journey. A mobile user can choose a scene or enter free text, see processing, then
  see four Chinese plan cards with real item images, roles, ownership, missing slots,
  scores, and model-written reasoning. The fallback remains visibly labelled and
  never impersonates model success.

## Surprises & Discoveries

- 2026-07-25: `_ref/video-branch-main` (Agent CLI / Skill / Playground reference) is
  not present in this workspace; the Skill entry and Playground are specified
  self-contained against the Product API instead of copied from the reference.
- 2026-07-25: No `look` table exists yet (Issue #3 is not merged). This Issue creates
  the minimal `look` persistence needed for `ai_generated` saves; schema must stay
  extensible for Issue #3 (feed_saved Looks, pending components) — coordinate via the
  Decision Log and an ADR if the shape becomes durable.
- 2026-07-25: The user-directed Skill DoD requires a directly executable
  `node scripts/match.js --wardrobe ... --request ...` contract before the shared
  Product API exists. The initial tracer implements that portable contract without
  fixed results. Before closing Issue #4, move the production planning authority
  behind the Product API and keep the CLI as a thin client so H5, Skill, and
  Playground cannot drift.
- 2026-07-25: A clean workstation lacked PostgreSQL, FFmpeg, and FFprobe. Full local
  verification used the repository's pinned PostgreSQL Compose service plus temporary
  media binaries; no test was skipped, and no media dependency was added to the
  product lockfiles.
- 2026-07-25: Browser testing exposed that a requested target item was described as a
  wardrobe gap. The fallback explanation now distinguishes “target item included” from
  genuinely missing slots, so a target coat plus missing shoes no longer claims the
  wardrobe lacks coats.
- 2026-07-25: A real Doubao Lite request through the local LiteLLM gateway completes
  in about 14.6 seconds even for a tiny two-plan payload. The earlier hard 15-second
  timeout caused valid four-plan responses to be cancelled at the boundary and shown
  as degraded. A later real four-plan request took slightly over 30 seconds, exposing
  the same false-failure at the 30-second boundary. The adapter now uses a shorter
  response contract and a configurable 60-second budget; plans still appear
  immediately from the deterministic candidate pass, while mobile verification
  returned `llm_ranked` with four genuine Chinese rationales before the final budget.

## Decision Log

- Plan generation progressively returns the deterministic candidates first and then
  the refined result from the same request stream. The bounded hosted reasoning phase
  never blocks the first usable plans; slot replacement is synchronous and
  deterministic because it only re-runs recall + rules for one slot.
- The LLM selects and orders from deterministic candidate combinations only; its
  output is schema-validated and re-checked by the rule engine. One retry on invalid
  output, then deterministic fallback with an explicit `rule_ranked` explanation state.
- Diversity is a deterministic pre-condition enforced at combination time (pairwise
  distance over item overlap, silhouette, palette, and style direction), not a prompt
  instruction — acceptance requires "not just reordering or different copy".
- Purchase list entries are `CommerceOffer`-shaped search demands (query, category,
  constraints, jump URL) because no real commerce API exists; no inventory/price
  fields are emitted at all rather than emitting fake ones.
- The hosted reasoning timeout is configurable and defaults to 60 seconds. Measured
  Doubao Lite requests range from about 15 seconds to slightly over 30 seconds, so
  both 15- and 30-second hard cutoffs create false failures. The product exposes the
  usable deterministic candidates immediately and still labels a genuine timeout as
  `degraded: true`; keys remain server-only environment values.

## Context and Orientation

### Domain vocabulary

Use `CONTEXT.md` terms: OutfitPlan (proposal with slots, constraints, explanations,
owned Items, missing slots), Look (saved relationship; `ai_generated` source),
OwnershipState (`owned / collected / wanted / purchased_pending`), PreferenceSignal
(replace/save/purchase events), CommerceOffer (time-varying purchasable info, not the
Item). An OutfitPlan becomes a Look only when saved.

### Reuse and best-practice audit

- **This repository (primary reuse).** Capture feature's idempotent job submission,
  Celery task shape, status/SSE plumbing (`features/capture/`); wardrobe domain
  (`features/wardrobe/domain.py` — `WardrobeItem`, `FieldEnvelope` provenance/locking,
  `ItemStatus`), repository and pgvector `embedding` column (provider-native
  dimensions, migration 0006); `features/wardrobe/taxonomy.py` for category
  normalization; platform config/session/errors; LiteLLM `reasoning` alias already in
  `config/litellm.yaml`; multimodal text/image embedding via the LiteLLM pass-through
  `/v1/embeddings/multimodal` for query-side embeddings.
- **`wardrowbe` (MIT, pinned c63ced9, in `_ref` catalog).** Adapt its outfit/garment
  relational modeling and async AI-provider boundary patterns; convert shapes into
  this project's `OutfitPlan`/`Look` contracts — never import its models directly.
- **Shopify `product-taxonomy` (MIT).** Source of the category vocabulary already
  localized in `taxonomy.py`; extend with a category → slot-role mapping (top, bottom,
  one_piece, outerwear, shoes, accessory) instead of inventing a parallel taxonomy.
- **Two-stage recommender practice (industry standard).** Candidate generation
  (cheap, high-recall SQL/pgvector) strictly before ranking; deterministic filters
  before any learned/generative ranker. This matches the acceptance requirement that
  hard rules run before generative re-rank.
- **LLM-as-reranker pattern.** The model receives a closed candidate list with ids
  and returns ids + explanations under a JSON schema; membership and constraint
  validation happen outside the model. This is the same boundary the ingest slice
  uses for `vision_understanding` output (schema-validated, taxonomy-normalized).
- **Outfit-composition research (Polyvore-style slot compatibility).** Slot-based
  composition with pairwise compatibility beats free-form generation for
  controllability; used as rationale for the slot/rule design, no code to reuse.
- **Anthropic Skill conventions.** The Skill entry is a `SKILL.md` + small script
  that calls the public Product API with the generated contract — the Skill never
  embeds business rules (per TECHNICAL-DECISIONS §9.4: H5 and Skill do not each
  write their own request structures).
- **Cold-start wardrobe reuse.** Reused the existing Capture idempotency contract,
  Wardrobe repository, Look aggregate/components, local object store, session
  bootstrap, taxonomy/provenance envelopes, and the already licensed Pexels Feed
  corpus. Rejected a frontend-only fixture because AI, detail views, filters, and
  later saves would observe different truth. No seed-only persistence or alternate
  API was introduced.
- **Recommendation tracer reuse.** Reused the existing WardrobeItem contracts,
  ownership/status semantics, generated OpenAPI client, LiteLLM `reasoning` alias,
  TanStack Query state handling, and StyleCapture card primitives. Adapted the
  closed-candidate reranker boundary from the Issue #4 Skill. Rejected copying the
  Skill algorithm into H5 or adding a second recommendation server; the remaining
  Skill implementation must become a thin Product API client before Issue #4 closes.

### Target file map

    services/backend/src/stylecapture_backend/features/outfit/
      __init__.py
      domain.py            # OutfitRequest, SlotRole, PlanSlot, OutfitPlan, RuleReport,
                           # DiversityReport, deterministic scoring — pure, no imports
                           # of FastAPI/SQLAlchemy/Celery/LiteLLM
      rules.py             # hard-rule engine: completeness per scene, one_piece vs
                           # top/bottom conflict, layering, season/weather, formality
                           # window, must-include/exclude, ownership availability
      application.py       # PlanOutfits, ReplaceSlot, SavePlanAsLook,
                           # GetPurchaseList, AdvancePurchaseState use cases
      ports.py             # CandidateRecall, AestheticReranker, PlanRepository,
                           # LookWriter, TraceRecorder protocols
      infrastructure/
        models.py          # outfit_request, outfit_plan, purchase_list_entry, look
        repository.py
        recall.py          # SQL + pgvector recall (owned → collected/wanted), query
                           # embedding via multimodal pass-through
        reranker.py        # LiteLLM `reasoning` adapter; prompt/schema versions here
        tasks.py           # Celery plan-generation job
      interfaces/
        http.py            # Product API routes (below)
    services/backend/migrations/versions/20260725_0007_outfit_planning.py
    services/backend/tests/outfit/          # domain, rules, diversity, application
    services/backend/tests/api/             # contract tests for new routes
    services/backend/tests/integration/     # job round-trip, replace, purchase list
    apps/h5/src/features/outfit/
      OutfitRequestScreen.tsx  PlanCards.tsx  PlanDetail.tsx
      SlotReplaceSheet.tsx  PurchaseListSheet.tsx  collage.ts
    apps/h5/src/features/playground/PlaygroundScreen.tsx   # trace viewer (dev entry)
    skills/scene-outfit-matching/SKILL.md
    skills/scene-outfit-matching/references/schema.md
    skills/scene-outfit-matching/references/prompt-design.md
    skills/scene-outfit-matching/scripts/match.js
    skills/scene-outfit-matching/assets/mock-wardrobe.json
    scripts/seed_dev_wardrobe.py

### Product API (contract truth = FastAPI OpenAPI; regenerate the TS client)

- `POST /v1/outfit-plans` — body: scene (required), weather?, style?, formality?,
  comfort?, anchor_item_id?, must_include_item_ids[], exclude_item_ids[],
  idempotency key header. Returns `202 {request_id, job_id}`.
- `GET /v1/outfit-plans?request_id=` — plan set with status
  (`processing / ready / partial / error`), 3–4 plans when ready.
- `GET /v1/outfit-plans/{plan_id}` — full plan: slots (item_id | missing), per-slot
  source/ownership/role/explanation, rationale, rule report, diversity axes,
  `is_fully_from_wardrobe`, explanation state (`llm_ranked | rule_ranked`), trace id.
- `POST /v1/outfit-plans/{plan_id}/replace` — `{slot_role}` → 200 with ranked
  candidates and the updated plan; only that slot recomputed, accepted slots kept.
- `POST /v1/outfit-plans/{plan_id}/save-look` — creates an `ai_generated` Look
  referencing the plan's owned/collected Items; records a PreferenceSignal.
- `GET /v1/purchase-lists/{plan_id}` — persisted entries for missing slots.
- `PATCH /v1/purchase-lists/{plan_id}/entries/{entry_id}` — state transition
  `wanted → purchased_pending → owned` (server-validated order; `owned` flips the
  linked Item's ownership through the existing user-truth-preserving path).
- `GET /v1/outfit-plans/{plan_id}/trace` — workflow evidence for Playground/review:
  rule version, recall counts per tier, dropped-by-rule counts, model/prompt/schema
  versions, latency. No secrets, no raw prompts with user media.

## Plan of Work

### Milestone 0: Seeded development wardrobe (small, first)

Write `scripts/seed_dev_wardrobe.py` inserting 15–20 diverse ready Items (tops,
bottoms, one-pieces, outerwear, shoes, accessories; mixed ownership owned/collected/
wanted; seasons; formality) for a dev user through the real repository contracts,
every field marked `curated_seed` provenance, images from existing local corpus
assets. Also add pytest fixtures building the same wardrobe in-memory via ports.
This unblocks all later milestones without waiting on live ingest, without runtime
mocks. Verify: script is idempotent (re-run creates nothing new), wardrobe screen
renders the seed honestly.

### Milestone 1: Pure outfit domain and hard rules

Red-green, no I/O. Slot taxonomy and category→role mapping on top of
`wardrobe/taxonomy.py`; `rules.py` engine returning a structured `RuleReport`
(which rule rejected which combination and why — this feeds explanations and the
trace); deterministic compatibility scoring (color harmony from item color fields,
formality/season fit, anchor adherence); pairwise diversity metric with a concrete
threshold; combination builder that emits 3–4 maximally-diverse valid combos.
Property-style tests: a one_piece combo never contains top or bottom; excluded ids
never appear; must-include ids appear in every plan or generation fails with an
explicit reason; diversity threshold holds for every emitted pair. Architecture test:
`check_boundaries.py` passes with the new module.

### Milestone 2: Persistence, recall, and the async plan API

Migration 0007 (outfit_request, outfit_plan with JSONB slots + versions, 
purchase_list_entry, minimal look). Recall adapter: SQL filters (user, status
ready/partial-usable, category in role, season/weather, not excluded) ordered
owned → collected/wanted, with pgvector similarity against the request text
embedded through the multimodal pass-through; per-tier candidate caps. Celery job:
recall → rules → combos → persist plans (`rule_ranked` state at this stage) →
purchase-list entries for missing slots. Routes wired with idempotency and SSE
completion; replace endpoint recomputes one slot deterministically; save-look and
purchase-state transitions enforced server-side. Integration tests against real
Postgres/Redis (existing test harness), including: replace keeps accepted slots,
double-submit with one idempotency key yields one request, purchase state cannot
skip `purchased_pending`.

### Milestone 3: Aesthetic re-rank and explanations through LiteLLM

`reranker.py` adapter calling the `reasoning` alias with a versioned prompt and a
strict JSON schema (ranked combo ids, per-slot explanation, rationale, style match
score). Validation: ids ⊆ candidates, rule engine re-check, schema parse; one retry;
otherwise keep deterministic order with explicit `rule_ranked` explanation state
surfaced by API and UI. Record trace (model/prompt/schema versions, latency,
validation outcome). Tests use a fake reranker through the port (valid, invalid-id,
rule-violating, timeout cases); one real smoke test against the live gateway records
a genuine trace id as evidence. Never let the adapter leak model ids into domain or
API responses.

### Milestone 4: H5 outfit journey

Request screen (scene text + optional weather/style/formality/comfort chips +
anchor-item picker from wardrobe); plan cards rendering an immediate collage from the
real item images (`collage.ts`, pure client composition of existing photos — a
deterministic view, not a RenderArtifact claim); plan detail with per-slot photo,
source, ownership badge, role, explanation, rationale, and explanation-state label;
slot replace sheet preserving accepted slots; purchase list sheet with search-demand
copy + jump links and state controls; save-as-Look with wardrobe visibility.
Regenerate the OpenAPI TS client (`pnpm contracts:generate`) — no hand-written
request shapes. Mobile Playwright E2E for the full journey including processing,
partial (missing slots), error, and rule_ranked-fallback states; visual review vs the
StyleCapture reference ≥ 90 per the contract.

### Milestone 5: Skill, Playground, evidence, and merge

`skills/scene-outfit-matching/`: concise SKILL.md plus progressive-disclosure
references, executable `match.js`, and a reviewed mock wardrobe. The script
authenticates with a normal session, submits a request, polls to ready, and prints
plans and trace id — same API, zero duplicated rules; include the cURL example in
`docs/api/`. Playground: dev H5 route rendering
`GET /v1/outfit-plans/{id}/trace` (rule version, tier counts, drops, model versions,
latency) for judges. Then: full CI-equivalent local run, real end-to-end smoke with
really-ingested items (not only the seed), screenshots of initial/interaction/
processing/success/failure/recovery states, spec/quality/architecture/UX reviews,
bounded cleanup, update Issue #4 with evidence, open PR to `main`, review, merge,
`git fetch origin --prune`, and confirm branch/PR/Issue state per `AGENTS.md`.

## Concrete Steps

    # sync before any work (AGENTS.md GitHub rule 4)
    git fetch origin main && git rebase origin/main   # or merge, keep linear if clean
    uv sync --all-packages && pnpm install --frozen-lockfile
    docker compose up -d postgres redis litellm       # existing compose services
    uv run alembic -c services/backend/alembic.ini upgrade head
    uv run python scripts/seed_dev_wardrobe.py --user dev

    # per-slice verification (must match CI)
    uv run ruff check services/backend/src services/backend/tests scripts
    uv run ruff format --check services/backend/src services/backend/tests scripts
    uv run mypy services/backend/src services/backend/tests scripts
    uv run python scripts/check_boundaries.py services/backend/src
    uv run pytest -q
    pnpm contracts:generate && git diff --exit-code -- apps/h5/openapi.json apps/h5/src/api/schema.d.ts
    pnpm typecheck && pnpm test && pnpm build

    git push -u origin codex/issue-4-scene-outfit-matching   # backoff 2s/4s/8s/16s on network failure

Commit after every green slice; small, reversible commits.

## Validation and Acceptance

Map one automated check to each Issue #4 acceptance box:

1. Single API accepts scene/weather/style/formality/comfort/must/exclude — contract
   test on `POST /v1/outfit-plans` + OpenAPI snapshot.
2. Re-rank/explanations via LiteLLM `reasoning`; rules/recall/state/purchase lists
   deterministic — architecture boundary test + reranker adapter tests + code review
   that no model call exists in rules/recall/state paths.
3. Recall order owned → collected/wanted → commerce, commerce only for missing
   slots — recall adapter tests with seeded tiers.
4. Hard rules before generative re-rank, one_piece conflict blocked, layering/
   season/weather/formality/excludes enforced — property tests in Milestone 1 plus a
   test that a rule-violating LLM response is rejected.
5. 3–4 structurally different plans — diversity threshold test (pairwise), plus a
   negative test that near-duplicate combos are not emitted.
6. H5 shows source/ownership/role/explanation and immediate real collage — Playwright
   assertions + screenshots.
7. Replace recomputes only the slot, keeps accepted parts, wardrobe-first —
   integration test comparing untouched slots byte-for-byte.
8. Missing slots → persisted purchase list; no fabricated inventory/price — schema
   has no price/stock fields; test asserts search demand + jump link shape.
9. Save as `ai_generated` Look; `wanted → purchased_pending → owned` — state-machine
   tests incl. illegal-transition rejection and user-truth-preserving ownership flip.
10. H5/Skill/Playground share one API, rule version, trace — Skill smoke run + trace
    endpoint test + generated-client-only check in H5; real smoke evidence attached
    to the Issue.

## Idempotence and Recovery

- `POST /v1/outfit-plans` is idempotent per key; retries return the same request/job.
- The generation job is retryable; a crash after recall re-runs deterministically
  (same rule version → same combos); LLM retry policy is bounded (1) with recorded
  outcome.
- Seed script and migration are re-runnable without duplication.
- If the gateway is down, plans still generate in `rule_ranked` state; the UI labels
  it and the trace records the failure — recovery is re-running re-rank, never
  fabricating an explanation.
- If `origin/main` moves mid-development (e.g. Issue #3 merges a Look table), stop,
  sync, reconcile schemas in a migration revision, and note it in the Decision Log
  before continuing (`AGENTS.md` GitHub rules 4–6).

## Outcomes & Retrospective

Issue #4 is implemented as one real Product API workflow shared by H5 and the
`scene-outfit-matching` Skill. Structured SQL recall filters status, ownership,
category and exclusions; pgvector orders semantically relevant candidates when an
embedding is present. The application validates weather, formality, season,
required roles, one-piece conflicts and structural diversity before the LiteLLM
adapter may re-rank the four legal plans.

Saving a plan creates an `ai_generated` Look without fabricated frame provenance,
persists each real Item reference, creates purchase demands only for missing pieces,
and independently queues its collage and pixel cover. A purchase demand linked to a
real inspiration Item moves that same Item to `owned` on receipt; unlinked commerce
search demands remain honest and require later photo recognition. The public trace
resource exposes only user-safe workflow steps, capability alias and internal
version, never prompt, media, provider endpoint or provider model identity.

Fresh evidence on 2026-07-26:

- backend: `247 passed`; Ruff format/check and Mypy (`135` files) passed;
- H5: `48 passed`, typecheck and production build passed;
- Skill: `4 passed`; OpenAPI generation was byte-stable on a second run;
- clean-database migration reached the single head `20260726_0014`, and Alembic
  detected no schema drift;
- real mobile E2E generated progressive plans through the configured LiteLLM
  provider, saved one valid 4-or-5-piece Look, displayed its genuine collage, then
  generated a private personal try-on in `1.6m`;
- screenshots include
  `artifacts/issue-4/ai-real-ranked-mobile-60s.png`,
  `artifacts/issue-4/wardrobe-seeded-mobile.png`, and the Issue #5 personal-render
  evidence linked below.

The only deliberately deferred work is deployment under Issue #6. No GPU server or
local heavyweight model is required for this slice.
