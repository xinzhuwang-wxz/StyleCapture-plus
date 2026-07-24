# StyleCapture-plus Agent Contract

This repository is developed as a continuous, evidence-driven product loop.

## Sources of truth

Read these before implementation:

1. The active Codex Goal.
2. The current GitHub Issue and its acceptance criteria.
3. `docs/product/PRD.md`.
4. `docs/architecture/TECHNICAL-DECISIONS.md`.
5. `CONTEXT.md` and applicable records under `docs/adr/`.
6. `docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md`.
7. `docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md`.

When sources conflict, preserve the active Goal, then update the lower-level artifact so the conflict does not recur.

## Continuous issue loop

Execute Issues in dependency order. Do not pause between completed Issues to ask whether to continue.

For every Issue:

1. Confirm dependencies and restate the observable user outcome.
2. Create or update a living ExecPlan under `docs/exec-plans/`.
3. Work on an Issue branch and keep commits small, reversible, and Lore-compliant.
4. Implement a complete vertical slice through UI, API, domain, persistence, jobs, and real provider boundaries as applicable.
5. Use behavior-first tracer bullets: one failing observable test, the minimum implementation, then the next behavior.
6. Run fresh verification. Never infer success from an earlier run or an agent report.
7. For visible behavior, operate the product as a user at mobile viewports, capture screenshots/video, and run visual review against the approved Feed and StyleCapture references. A visible milestone requires a Visual Verdict score of at least 90.
8. Run separate spec-compliance, code-quality/security, architecture, and user-experience reviews. Fix blocking findings in the same Issue.
9. Run bounded code cleanup on changed files, then repeat verification.
10. Update the Issue with evidence, add or amend ADRs when a durable decision changed, push the branch, open/review/merge the PR, and immediately continue to the next unblocked Issue.

An Issue is not complete when only the happy-path code exists. Its acceptance criteria, failure states, real evidence, visual quality, and cross-layer contracts must all pass.

For user-visible work, browser automation must follow the real mobile journey and save screenshots for the changed initial, interaction, processing, success, failure, and recovery states. DOM assertions alone are insufficient.

## Discovery and steering

Classify findings during development:

- A defect or missing acceptance detail inside the current slice: fix it in the current Issue.
- A newly discovered requirement needed for the current user outcome: amend the current Issue and its ExecPlan.
- A durable cross-cutting decision about domain contracts, data ownership, provider boundaries, security, privacy, deployment, or compatibility: add or supersede an ADR and update affected Issues.
- Truly independent optional work: create a bounded follow-up Issue. Do not use follow-up Issues to hide incomplete acceptance criteria.

Record evidence in the living ExecPlan under `Surprises & Discoveries` and decisions under `Decision Log`.

## Runtime truthfulness

- Runtime and judging environments must not return mock, stub, prompt-keyed, or fixed business results.
- Tests may use fakes only through the same public provider contracts.
- LiteLLM is the application model gateway. Domain, application, UI, and API modules use capability contracts and aliases; only infrastructure adapters may know provider model IDs or payloads.
- The Feed demo corpus may be manually pre-tagged by the development agent only when every annotation is marked `curated_seed`. Never present curated metadata as a live or cached model result.
- New user inputs and uncached intelligent workflows must use the real configured model provider. Codex develops and verifies the product; it is never a runtime inference provider.
- Provider keys are server-only environment/secret values and must not appear in commits, browser bundles, fixtures, traces, screenshots, or logs.
- Without a GPU server, continue using real hosted providers, genuinely runnable lightweight models, or an explicitly labelled deterministic product fallback such as a real-item collage.
- Server rental and self-hosted heavy-model smoke tests belong to Issue #6 and must not block Issues #1–#5.

## Code organization

- Organize each product capability as a vertical module with explicit `domain`, `application`, `infrastructure`, and `interface` boundaries.
- Keep domain entities, value objects, invariants, and policies pure. They must not import FastAPI, SQLAlchemy, Celery, LiteLLM, React, storage SDKs, or provider payload types.
- Application use cases orchestrate domain behavior through typed ports. Infrastructure adapters implement persistence, queues, object storage, LiteLLM, segmentation, embeddings, commerce, and rendering.
- HTTP handlers, workers, UI components, and Skill entry points translate transport data and call application use cases; they do not contain duplicated business rules.
- Shared contracts are versioned and generated where possible. Provider DTOs never become Product API or domain contracts.
- Prefer cohesive feature modules and small named files over layer-wide dumping grounds. Do not create generic `utils`, `helpers`, `common`, or `manager` modules without a single explicit responsibility.
- Do not introduce an abstraction for one speculative implementation. Add a port when there are multiple adapters, a test seam, or a real external boundary.
- Enforce dependency direction with lint/static architecture tests, keep public APIs documented, and delete superseded code in the same Issue.

## Reuse before invention

Audit `_ref/README.md` and the referenced source before adding new foundations. Reuse or adapt proven code, assets, schemas, tests, and provider contracts when licenses and product constraints permit. Do not import reference repositories wholesale or preserve their internal architecture when a smaller compatible extraction is sufficient.

## Laptop resource safety and portability

Follow `docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md`.

- Prefer the Docker Compose `core` profile for portable local services.
- Do not run heavyweight VLM/try-on workloads or concurrent media batches on the laptop.
- Before and during long builds, E2E runs, or processing, inspect system and container CPU, memory pressure, thermal state, swap, and free disk at least every five minutes.
- Reduce concurrency or stop the expensive process when a guard trips. Never trade sustained full-machine load for speed.
- Keep CUDA and heavy providers in optional images so core development and tests remain portable and usable without a GPU.

## Feed corpus

Maintain a provenance-recorded local Feed corpus with at least 30 varied authorized/public demo samples. Include single garments, multi-item outfits, accessories, layering, motion, occlusion, low contrast, and difficult negative cases. Do not rely on a tiny hand-picked happy-path set.

## GitHub and completion

The agent may manage branches, commits, pushes, PRs, labels, Issues, comments, and merges for this repository. Never rewrite unrelated user work or use destructive Git operations.

Do not mark the aggregate Goal complete until:

- Issues #1–#6 are closed or explicitly superseded with evidence.
- All PRD P0 user stories are demonstrable end to end.
- Fresh automated, real-provider, browser, visual, security, privacy, and architecture evidence passes.
- No unresolved P0/P1 defect remains.
- Final cleanup and independent code review return clean verdicts.
