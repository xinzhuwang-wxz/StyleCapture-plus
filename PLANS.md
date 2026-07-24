# Codex ExecPlans

Substantial work in this repository uses a living ExecPlan. An ExecPlan must be sufficient for another engineer or agent to resume without reconstructing decisions from chat history.

## Required sections

Every plan under `docs/exec-plans/` contains:

- `Purpose / Big Picture`: the user-visible outcome and how to observe it.
- `Progress`: timestamped checkboxes updated at every meaningful pause.
- `Surprises & Discoveries`: unexpected behavior with concrete evidence.
- `Decision Log`: decisions, rationale, date, and affected contracts.
- `Context and Orientation`: relevant domain terms, modules, references, and environment assumptions.
- `Plan of Work`: vertical milestones ordered by dependency.
- `Concrete Steps`: commands, working directory, and expected observable outputs.
- `Validation and Acceptance`: exact automated, real-provider, browser, and visual checks.
- `Idempotence and Recovery`: safe retry, rollback, and partial-failure behavior.
- `Outcomes & Retrospective`: delivered behavior, evidence, remaining non-blocking limitations, and lessons.

## Plan rules

- Keep the document current while work proceeds; it is not a one-time forecast.
- Milestones tell a sequence of goal → work → result → proof.
- Acceptance is observable behavior, not a file inventory or “implementation complete”.
- Prefer one tracer-bullet vertical path at a time.
- Record discoveries immediately instead of relying on conversation memory.
- If evidence changes the design, update the plan, affected GitHub Issue, and an ADR when the decision is durable.
- Move directly to the next milestone without a permission handoff unless an irreversible, destructive, credential-gated, or materially scope-changing decision is required.
- A deployment credential or unavailable heavy GPU is not a blocker for Issues #1–#5.
