# Autonomous Development Loop

状态：Active
日期：2026-07-25

## Direct recommendation

Use four coordinated layers:

1. **Aggregate Goal** owns the terminal outcome and prevents premature stopping.
2. **Continuous Issue Loop** implements one dependency-ordered vertical slice at a time without human handoffs between Issues.
3. **Thread Heartbeat** returns to the same context every two hours to audit trajectory and steer the loop; it is not a concurrent second implementer.
4. **Milestone Quality Gate** runs after every Issue and at major UI/API/domain milestones.

Goal is the engine. Scheduled automation is the metacognitive reviewer. GitHub Issues, ExecPlans, ADRs, tests, traces, screenshots, and PR history are durable memory.

## Why this shape

OpenAI recommends verifiable Goals rather than vague “implement the plan” objectives, and describes thread automations as recurring wake-ups that preserve the same conversation context. Its scheduled-task guidance recommends durable prompts that specify what to do, when to report, and when to stop. OpenAI’s ExecPlan example treats progress, discoveries, decisions, and outcomes as living state rather than chat-only memory.

Community practice adds three useful controls: keep iterations bounded by acceptance criteria, require fresh verification before completion claims, and separate specification review from code-quality review. A raw infinite shell loop is therefore unnecessary here; Codex Goal supplies persistence while the repository and GitHub provide inspectable state.

Primary references:

- OpenAI, [Scheduled tasks](https://learn.chatgpt.com/docs/automations)
- OpenAI, [Codex-maxxing for long-running work](https://cdn.openai.com/pdf/8a9f00cf-d379-4e20-b06f-dd7ba5196a11/OAI_WhitePaper_Codex-maxxing26.pdf)
- OpenAI Agents Python, [Codex Execution Plans](https://github.com/openai/openai-agents-python/blob/main/PLANS.md)
- OpenAI, [How OpenAI uses Codex](https://cdn.openai.com/pdf/6a2631dc-783e-479b-b1a4-af0cfbd38630/how-openai-uses-codex.pdf)
- Superpowers, [subagent-driven development and verification](https://github.com/obra/superpowers)
- Geoffrey Huntley, [Ralph Wiggum technique](https://github.com/ghuntley/how-to-ralph-wiggum)

## Continuous loop

The controller repeatedly:

1. Reads the aggregate Goal, GitHub dependency graph, current Issue, ExecPlan, relevant ADRs, and latest merged evidence.
2. Selects the first unblocked Issue.
3. Creates an Issue branch and records the starting baseline.
4. Executes vertical tracer bullets using public-interface tests.
5. Exercises real provider boundaries without requiring a rented GPU server.
6. Checks local CPU, memory pressure, thermal state, disk and Docker usage before and during expensive work; reduces concurrency instead of sustaining full-machine load.
7. Runs automated checks and then operates the H5 as a real user.
8. Captures mobile screenshots and interaction recordings for Feed, wardrobe, processing, failure, and recovery states.
9. Runs independent spec, code/security, architecture, and UX/visual review.
10. Fixes blocking findings in the same Issue, performs bounded cleanup, and repeats all affected checks.
11. Updates the Issue, ExecPlan, ADRs, and PR evidence; merges only when clean.
12. Immediately starts the next unblocked Issue.

## Two-hour heartbeat

The heartbeat inspects the same thread and checkout. It does not create a parallel implementation branch.

It checks:

- whether the current work still advances the active Goal and current Issue;
- acceptance criteria with no recent evidence;
- failing/disabled tests, runtime mocks, hardcoded fixtures, TODO tails, or hidden fallbacks;
- curated Feed annotations being misrepresented as runtime AI, or new user inputs bypassing the LiteLLM provider boundary;
- frontend/backend/schema/task-state drift;
- dependency-direction violations, provider leakage, oversized or shallow modules, duplication, generic dumping grounds, and abstractions without a real boundary;
- browser-visible UX problems at mobile viewports;
- whether a discovery requires an Issue amendment, a new bounded Issue, or an ADR;
- whether lack of GPU/server access is being incorrectly treated as a blocker.
- whether the laptop or Docker containers are under sustained resource pressure, and whether local work should be serialized or moved behind a hosted provider.

The heartbeat fixes safe local P0/P1 findings immediately, reruns affected checks, and records the decision. It reports only material changes, blockers, or a clean audit summary.

## Milestone quality gate

Run after every Issue and whenever a public contract, domain invariant, or major visible journey changes:

1. `$verify`: fresh tests, typecheck, build, contract checks, real provider smoke, and failure-path evidence.
2. Real-user browser pass: upload/camera, Feed pause/lasso/swipe, processing/retry, wardrobe browsing, Look detail, recommendation, replacement, and save.
3. `$visual-verdict`: compare approved Feed and StyleCapture references; target score ≥ 90 at recorded mobile viewports.
4. `$code-review`: independent spec/security/quality review plus architecture devil’s-advocate lane.
5. `$improve-codebase-architecture`: use only when real friction exists; apply the deletion test and respect ADRs.
6. Bounded `ai-slop-cleaner` on changed files, followed by the full affected verification set again.

`APPROVE + CLEAR`, no P0/P1 defect, and fresh visual/user evidence are required before merge.

## ADR and Issue steering

Create or supersede an ADR only for a durable choice affecting external contracts, domain invariants, ownership of data, provider seams, security/privacy, deployment topology, or compatibility. Tactical implementation discoveries belong in the ExecPlan.

Amend the current Issue when a discovered requirement is necessary for its user outcome. Create a new Issue only for independently valuable work that cannot be completed safely inside the current slice. Never create a follow-up Issue to avoid fixing failed acceptance.

## Feed corpus

Issue #2 maintains a local corpus of at least 30 provenance-recorded, authorized/public demo samples. The corpus must cover:

- single garments and full Looks;
- multiple selected garments in one frame;
- hats, shoes, bags, jewelry, tops, bottoms, dresses, and outer layers;
- motion blur, partial occlusion, low contrast, busy backgrounds, and negative/non-fashion frames;
- varied aspect ratios and camera distances.

Use a fixed evaluation subset for regression while keeping a larger browsing library for judge interaction. Preserve source URL/owner, permission or usage note, content hash, duration, and representative-frame metadata.

The development agent may pre-tag this known corpus without calling a paid model. Store those annotations as reviewed `curated_seed` metadata. They are browsing/regression inputs, not real-provider acceptance evidence. New user content and uncached workflows must still use the LiteLLM-routed product models.

## Stop conditions

Continue automatically while safe, scoped work remains.

Pause only for an irreversible/destructive action, a credential-gated external production action that cannot be substituted, or a product choice that materially changes the Goal. A missing GPU server is not such a blocker.

Stop the heartbeat and complete the Goal only after the PRD, Issues, quality gates, real-user journeys, and final review are all satisfied.

## Launch prompts

### Aggregate Goal

```text
Deliver StyleCapture-plus as a review-ready mobile AI digital wardrobe product that satisfies docs/product/PRD.md and GitHub Issues #1–#6. Complete Issues continuously in dependency order using real data and real lightweight, hosted, or later self-hosted providers behind stable APIs; never use runtime mocks or fixed results. Route product-time reasoning, vision understanding, and image generation through LiteLLM capability aliases; keep provider details in infrastructure adapters and secrets server-side. The development agent may manually pre-tag the known Feed corpus as curated_seed metadata without consuming model APIs, but new user inputs and uncached intelligent workflows must use real model calls and Codex must never act as runtime intelligence. Preserve the approved Douyin-style Feed interaction and StyleCapture pixel-purple wardrobe identity, maintain a provenance-recorded Feed corpus of at least 30 varied samples, and keep readable feature-local domain/application/infrastructure/interface boundaries across frontend, API, persistence, workers, Skill, and render artifacts. Develop the portable core through Docker Compose, keep heavy AI outside the laptop, monitor CPU/memory pressure/thermal state/disk/container usage during long work, and reduce concurrency whenever resource guards trip. For every milestone, verify automated behavior, dependency direction and live provider evidence; operate the interface as a real mobile user; capture screenshots for changed interaction, processing, success, failure and recovery states; run independent spec/code/security/architecture/UX reviews; fix P0/P1 findings in the same Issue; remove redundant code; and record durable discoveries in ExecPlans, ADRs, and GitHub. Manage branches, commits, pushes, PRs, merges, Issues, and ADRs autonomously. Defer server rental until measured need; absence of a GPU server must not stop Issues #1–#5. Complete only when all acceptance criteria have fresh evidence, all required PRs are merged, no unresolved P0/P1 remains, and final review is APPROVE + CLEAR.
```

### Continuous Issue Loop

```text
Run the StyleCapture-plus continuous issue loop defined in AGENTS.md and docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md. Read the active Goal and GitHub state, choose the first unblocked Issue, create/update its living ExecPlan, implement the complete vertical slice with behavior-first tracer bullets, verify every acceptance criterion with fresh evidence, exercise the mobile UI as a real user, run visual/spec/security/architecture reviews, fix blocking findings, clean changed code, rerun verification, update ADRs/Issues when discoveries justify it, merge the reviewed PR, and immediately continue to the next unblocked Issue. Do not pause between Issues and do not treat missing GPU infrastructure as a blocker.
```

### Scheduled Heartbeat

```text
Audit the active StyleCapture-plus development loop in this same thread. Read the active Goal, current GitHub Issue/PR, living ExecPlan, ADRs, recent diff/commits, test output, traces, and browser/visual evidence. Check goal alignment, missing acceptance evidence, hidden mocks or fixed results, curated_seed data being misreported as AI, new user inputs bypassing LiteLLM, leaked provider details or secrets, frontend/API/domain/worker drift, dependency-direction violations, UX failure states, visual fidelity, duplication, generic dumping grounds, shallow modules, and whether the implementation is incorrectly waiting for a GPU server. Inspect CPU, memory pressure, thermal indicators, swap, free disk and Docker usage; stop duplicate work and reduce concurrency if local resource guards are exceeded. Operate the current mobile build as a user when it is runnable and require screenshots for the changed initial, interaction, processing, success, failure and recovery states. Fix safe in-scope P0/P1 findings immediately and rerun affected verification. Amend the current Issue or ExecPlan when required; add/supersede an ADR for durable cross-cutting decisions; create a new Issue only for independent work, never to defer failed acceptance. Then resume the continuous issue loop. Report only material corrections, blockers, or a concise clean-audit result. If the aggregate Goal is complete, disable this heartbeat.
```

### Milestone Review

```text
Run the StyleCapture-plus milestone gate against the current Issue and active Goal. Use $verify for fresh evidence; test public behavior and failure recovery; operate all affected mobile journeys in the browser; capture screenshots/video and require $visual-verdict score >= 90 against approved Feed and StyleCapture references; run $code-review with separate spec/security/quality and architecture lanes; run $improve-codebase-architecture only on evidence-backed friction; apply bounded ai-slop-cleaner to changed files; rerun all affected checks. Fix every P0/P1 and any merge-blocking finding in the current Issue. Update the ExecPlan, ADRs, Issue, and PR with evidence. Return a clean verdict only when code review is APPROVE, architecture is CLEAR, and the observed product behavior matches the acceptance criteria.
```
