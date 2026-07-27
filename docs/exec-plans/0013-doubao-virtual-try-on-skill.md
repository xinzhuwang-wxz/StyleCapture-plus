# ExecPlan 0013: Package the Doubao virtual try-on skill

Status: Implemented, pending PR review
Date: 2026-07-26
Issue: User-requested standalone skill PR; no GitHub issue assigned

## Observable outcome

A Codex user can install one source folder or deterministic ZIP, provide a real
person photo plus one or more outfit-board images, and receive audited
photorealistic try-on results generated only through the selected Volcengine Ark
models. Multiple outfits for the same person share one canonical
identity/body/camera anchor so face, head scale, proportions, crop, and framing do
not drift independently.

The public usage and output contract is documented in
[`docs/doubao-virtual-try-on.md`](../doubao-virtual-try-on.md).

## Scope

- Add the reusable Codex skill source and agent metadata.
- Support single-outfit and identity-locked batch workflows.
- Document authentication, CLI options, outputs, exit codes, retries, costs,
  privacy, and failure recovery.
- Add deterministic packaging, secret rejection, and offline contract tests.
- Record the narrow provider-bound exception as a Proposed ADR.

## Non-goals

- No H5, Product API, Worker, persistence, or OpenAPI changes.
- No change to the product `look.virtual_try_on` capability or its providers.
- No checked-in generated photos or live-provider evidence.
- No automatic merge; the architecture exception requires PR review.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source commit / license |
| --- | --- | --- | --- | --- |
| Product virtual try-on | `services/backend/.../features/render`, `look.virtual_try_on` | Rejected for the standalone artifact; retained for product runtime | Existing flow correctly owns authenticated Looks, object keys, jobs, traces, and LiteLLM/FASHN providers, but it does not provide the required deploy-free two-local-image contract | StyleCapture-plus `87dd81c`; repository license |
| Codex Skill shape | `skills/scene-outfit-matching` | Adapted reuse | Reused `SKILL.md` + `agents/openai.yaml` discovery shape and repository placement; did not copy its Product API request semantics | StyleCapture-plus `87dd81c`; repository license |
| HTTP, image transport, packaging | Python `urllib`, `base64`, `json`, `zipfile` | Direct reuse | Standard library covers HTTPS, data URLs, JSON, and deterministic ZIPs without adding a dependency | CPython standard library; PSF License |
| Visual understanding and generation | Volcengine Ark chat/image generation APIs | Direct reuse | Exact hosted API and model versions selected by the user; no local model or alternate provider is allowed | Provider API; service terms |
| Existing external implementation | Current repository, `_ref/README.md`, mature try-on providers in ADR-0004 | Rejected copying | Product providers solve a different persisted runtime contract; no third-party source code is copied into the skill | Audit at StyleCapture-plus `87dd81c`; N/A |

## Progress

- [x] Reproduce the direct Ark understanding → generation → audit chain.
- [x] Add a single-look CLI with bounded retry and sanitized response logs.
- [x] Add a batch CLI with one canonical identity anchor and strict cross-look
  consistency audit.
- [x] Add install, API, output, error, privacy, and troubleshooting docs.
- [x] Add version reporting, deterministic packaging, and offline tests.
- [x] Validate that likely provider credentials and generated artifacts are absent
  from the diff.
- [ ] Obtain PR review for the Proposed ADR and standalone/product boundary.

## Surprises and discoveries

- The initial local checkout pointed at a different repository. The mistakenly
  pushed branch was removed before any PR existed, then the work was rebased onto
  `xinzhuwang-wxz/StyleCapture-plus/main`.
- StyleCapture-plus ADR-0005 intentionally forbids provider-bound Product Skills.
  The direct Ark requirement therefore needs an explicit, narrow Proposed ADR
  rather than being presented as an ordinary Product API facade.
- A cropped portrait can lock consistency across generated looks but cannot prove
  the person's real full-body proportions. Documentation requires a full-body
  reference when true-body fidelity matters.

## Decision log

- Use the single-look entry point only for exactly one outfit board.
- Use the batch entry point for two or more boards; never launch independent
  single-look jobs for a same-person set.
- Pin understanding/audit to `doubao-seed-2-0-lite-260428` and generation to
  `doubao-seedream-5-0-260128`.
- Keep provider failures truthful and stop; never use a local or alternate AIGC
  fallback.
- Keep the Proposed exception outside every StyleCapture product runtime path.

## Verification

- `pnpm test:doubao-skill`
- Codex skill-creator `quick_validate.py`
- deterministic package build repeated with matching SHA-256
- `git diff --check`
- repository Python format, lint, and type gates for changed root scripts
- secret-pattern scan across all PR files
- full repository CI as available; no paid Ark request is part of offline CI

Fresh local results:

- Doubao skill: 2 tests passed; structure validation passed.
- H5: 83 tests passed; typecheck and production build passed.
- Existing `scene-outfit-matching` skill: 4 tests passed.
- Python: ruff lint/format and architecture boundaries passed; 285 tests
  passed. Four media tests require local `ffmpeg`/`ffprobe`, which GitHub CI
  installs explicitly.
- Full mypy reproduced eight current-main Celery/Kombu import-stub errors in
  unchanged files. The changed root packager passes mypy independently.
- No live or paid Ark call was performed as part of PR verification.
