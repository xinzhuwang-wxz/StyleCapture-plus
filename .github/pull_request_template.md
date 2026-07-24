## Outcome

Describe the observable user outcome and link the Issue/ExecPlan.

## Reuse audit — required

| Capability | Candidates inspected | Decision | Reason | Source commit / license |
| --- | --- | --- | --- | --- |
|  |  | Direct reuse / adapted reuse / rejected |  |  |

- [ ] I inspected the current repository, `_ref/README.md`, relevant reference source,
  mature packages/open-source projects, and hosted APIs before implementing.
- [ ] The diff does not duplicate an existing frontend, backend, Worker, provider,
  domain contract, coordinate transform, state machine, or generated API client.
- [ ] Copied or adapted code records its upstream URL, exact commit, license, and local
  modifications.
- [ ] Rejected reuse has evidence: incompatible license/semantics/security or measured
  quality/performance—not preference.
- [ ] No whole reference repository or unused large dependency entered product code.

Missing evidence or unjustified duplicate implementation is a P1 merge blocker.

## Verification

- [ ] Fresh targeted and regression tests pass.
- [ ] Generated contracts have no drift.
- [ ] Real mobile user journey and changed visual states were inspected.
- [ ] Security, privacy, architecture, resource, and failure-recovery checks pass.
- [ ] No runtime mock, fixed result, secret leak, or `curated_seed` presented as AI.

## Evidence

List test commands, trace/screenshot paths, provider smoke evidence, and known
non-blocking limitations.
