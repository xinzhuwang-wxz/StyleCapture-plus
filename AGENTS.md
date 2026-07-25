# StyleCapture-plus Agent Contract

This repository is developed as a continuous, evidence-driven product loop.

## Sources of truth

Read these before implementation:

1. The active Codex Goal.
2. `plan.md`.
3. The current GitHub Issue and its acceptance criteria.
4. `docs/product/PRD.md`.
5. `docs/architecture/TECHNICAL-DECISIONS.md`.
6. `CONTEXT.md` and applicable records under `docs/adr/`.
7. `docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md`.
8. `docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md`.

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

Audit the current repository, `_ref/README.md`, referenced source, selected open-source
projects, mature packages, and available hosted APIs before adding a new foundation,
algorithm, contract, component system, or provider implementation.

Every Issue ExecPlan and PR must contain a compact reuse audit:

`capability -> candidates inspected -> direct reuse / adapted reuse / rejected -> reason -> source commit and license`

Missing this audit before a new implementation, duplicating an existing frontend,
backend, Worker, or provider capability, or manually maintaining a contract that can be
generated is a P1 merge blocker. Fix it in the current Issue; do not defer it.

Prefer deletion and direct reuse first, then a thin feature-local adapter around a
mature capability. Write a new implementation only when license incompatibility,
contract semantics, security, measured quality, or measured performance makes reuse
unsuitable, and record that evidence in the ExecPlan. Preserve source URL, exact commit,
license, local modifications, and upstream tests for copied code. Do not import
reference repositories wholesale, copy unused subsystems, or add a large dependency
merely to claim reuse.

## Laptop resource safety and portability

Follow `docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md`.

- Prefer the Docker Compose `core` profile for portable local services.
- Do not run heavyweight VLM/try-on workloads or concurrent media batches on the laptop.
- Before and during long builds, E2E runs, or processing, inspect system and container CPU, memory pressure, thermal state, swap, and free disk at least every five minutes.
- Reduce concurrency or stop the expensive process when a guard trips. Never trade sustained full-machine load for speed.
- Keep CUDA and heavy providers in optional images so core development and tests remain portable and usable without a GPU.

## Feed corpus

Maintain a provenance-recorded local Feed corpus with at least 30 varied authorized/public demo samples. Include single garments, multi-item outfits, accessories, layering, motion, occlusion, low contrast, and difficult negative cases. Do not rely on a tiny hand-picked happy-path set.

The development agent owns sourcing and downloading public Feed material for this non-commercial judging demo. Preserve source URLs, creator/platform labels when visible, hashes, and replacement notes, but do not block implementation on a commercial-grade rights-clearance workflow. Never include private, paywalled, leaked, or unlawfully obtained media.

## GitHub and completion

The agent may manage branches, commits, pushes, PRs, labels, Issues, comments, and merges for this repository. Never rewrite unrelated user work or use destructive Git operations.

为保证多人协作下的 GitHub 项目有序推进，请每位 Agent 持续监控本项目的 PR、Issue、提交记录与分支状态，并遵循以下规则：

1. 发现新的 PR、Issue、审查意见或 CI 状态变化时，及时处理并同步相关进展。
2. 对 PR 按 GitHub 协作规范进行审查：确认需求范围、代码质量、测试与 CI 结果、潜在冲突及对现有功能的影响。
3. 审查无误且具备合并权限时，及时合并；发现问题时，优先在 PR 中提出明确意见或直接在授权范围内修复，完成复核后再决定是否合并。
4. 开始开发、继续开发、提交或合并前，先检查远端最新 commit 与目标分支状态；本地落后时必须先同步并处理冲突，避免基于过期代码继续工作。
5. 每次 PR 合并后，及时拉取远端最新变更并确认本地工作分支、目标分支与 GitHub 状态一致。
6. 不覆盖、不回退他人的有效改动；对冲突、异常 CI、权限不足或存在合并风险的情况，及时记录并通知相关负责人。
7. 监控的目标是保持本地代码、远端分支、PR 状态和 Issue 处理进度持续一致，确保所有开发都基于最新、可验证的项目状态推进。

Do not mark the aggregate Goal complete until:

- Issues #1–#6 are closed or explicitly superseded with evidence.
- All PRD P0 user stories are demonstrable end to end.
- Fresh automated, real-provider, browser, visual, security, privacy, and architecture evidence passes.
- No unresolved P0/P1 defect remains.
- Final cleanup and independent code review return clean verdicts.
