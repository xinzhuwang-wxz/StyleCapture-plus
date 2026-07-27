# StyleCapture Journey Planning Review

- Date/time: 2026-07-28 00:14 CST
- Milestone / Issue / PR: pre-Goal commercial discovery and planning baseline; no Issue or PR yet
- Fixed diff base: `origin/main@fb4b9c0e04158cb82279426727bcdc8fb073491a`
- Reviewed planning content commit: `5bac2ff`
- Branch: `codex/stylecapture-journey`
- Scope: market hypothesis, product contract, iOS/backend/AI/deployment architecture, reuse/license choices, privacy/security gates, Skill boundary, implementation sequencing, and Goal stop conditions
- Excluded scope: app implementation, production deployment, Apple review, production payment evidence, real-provider quality evidence, and production cohort outcomes
- Evidence root: the versioned documents linked below in this repository; web source URLs, retrieval dates, exact OSS versions/commits, and licenses are recorded in the research/reuse audit

## Independent reviewers

| Review lane | Reviewer | Final verdict |
|---|---|---|
| Product, growth, conversion, falsifiability | `product_growth` | APPROVE + CLEAR |
| Native iOS and Apple delivery feasibility | `ios_stack` | APPROVE + CLEAR |
| Backend, scale, AI platform, Skill boundary | `backend_scale` | APPROVE + CLEAR after the capability registry and boundary tests were added |
| Privacy, security, China launch controls | `privacy_launch` | APPROVE + CLEAR |
| Adversarial implementation readiness | `plan_critic` | APPROVE + CLEAR |

## Findings and resolutions

| Severity | Contract | Finding | Resolution |
|---|---|---|---|
| P1 | M0 validation | A fixed 37-day deadline could precede `trip_end+7d` maturity and bias the cohort. | Removed the fixed deadline. Recruiting and the single ¥12 offer finish in seven days; GO waits for at least 15 mature plan recipients and records the actual cutoff. |
| P1 | Commercial metrics | Earlier drafts left denominators, VSS adoption, threshold boundaries, and TestFlight-versus-production evidence open to interpretation. | Frozen event definitions, mature cohort cutoffs, half-open iterate bands, initial 200/20 and scale 500/50 gates, and any-trigger kill rules in the PRD and Goal. |
| P1 | iOS delivery | Dependency locking, generated-project CI discovery, background task identifiers, renewal UX, and framework evidence were underspecified. | Fixed Xcode/Swift baseline and exact package revisions, versioned `Package.resolved` workflow, clean-checkout CI proof/fallback, fixed task identifiers, and concrete renewal files/tests. |
| P1 | Privacy and evaluation | Observability deletion, backup semantics, Promptfoo controls, retention, and privacy-canary coverage were incomplete. | Added the deletion index, active-store deletion versus backup expiry/cryptographic erasure, quarantine tombstone replay, complete retention coverage, exact Promptfoo flags, lock/SBOM controls, expanded negative canaries, and a metadata positive control. |
| P1 | Skill architecture | Existing Skills were demo wrappers or a provider-bound standalone artifact, not commercial Journey capabilities. | Added the Journey capability registry. P0 exposes no public Skill; App Intents and future agent surfaces are thin Product API adapters and cannot own providers, prompts, rules, persistence, entitlement, cost, or deletion. The Doubao standalone Skill is excluded from Journey runtime and evidence. |
| P1 | Implementation readiness | OpenAPI output paths, negative entitlement behavior, reuse decisions, and several verification commands were not executor-complete. | Added deterministic dual OpenAPI export/check paths, `PAYWALL_REQUIRED` and refund/revoke behavior, per-capability reuse audit, explicit files, tests, commands, and milestone review gates. |

No unresolved P0 or P1 remained after the final review round.

## Reviewed artifacts

- `docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md`
- `docs/product/STYLECAPTURE-JOURNEY-PRD.md`
- `docs/architecture/STYLECAPTURE-JOURNEY-TECHNICAL-DESIGN.md`
- `docs/architecture/JOURNEY-SKILL-CAPABILITY-REGISTRY.md`
- `docs/adr/0007-native-ios-trip-planning-and-storekit.md`
- `docs/exec-plans/0043-stylecapture-journey-commercial-app.md`
- `docs/superpowers/plans/2026-07-27-stylecapture-journey.md`
- `docs/engineering/STYLECAPTURE-JOURNEY-GOAL.md`

## Verification rerun

| Command | Time | Result |
|---|---|---|
| Targeted H5 restored-processing test | 2026-07-28 00:17 CST | 1 passed; confirmed the asynchronous test correction |
| `pnpm test` | 2026-07-28 00:17 CST | 239 passed: 228 H5, 5 scene-outfit Skill, 6 standalone Doubao Skill |
| `uv run pytest -q` | 2026-07-28 00:18 CST | 301 passed |
| `git diff --check` | 2026-07-28 00:18 CST | clean |

The H5 timing correction changes only a test: it replaces a synchronous lookup behind an asynchronous wardrobe load with a bounded observable lookup, then retains the terminal-removal and storage-cleanup assertions. These tests protect the reusable repository baseline; they do not count as iOS, production, real-provider, Apple sandbox, privacy-canary, or commercial evidence. Those remain milestone gates in the implementation plan and Goal.

## Verdict

`APPROVE + CLEAR` for launching the M0 Goal from this reviewed planning baseline. This is not approval to bypass M0 or claim the app is implemented, deployed, or commercially validated.
