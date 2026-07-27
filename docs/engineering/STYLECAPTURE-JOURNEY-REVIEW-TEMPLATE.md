# StyleCapture Journey Review Record

Copy this file into the current milestone evidence directory for every independent review. Chat-only verdicts are not completion evidence.

- Date/time:
- Milestone / local task / commit:
- GitHub Issue / PR: leave blank and do not read, create, edit, comment on, close, or otherwise operate Issues/PRs unless a future task explicitly authorizes it.
- Reviewer identity and role:
- Review type: spec | reuse/license | architecture | security/privacy | code quality | conversion/UX
- Fixed git commit and diff base:
- Scope and excluded scope:
- Evidence inspected: tests, traces, Promptfoo run, API diff, screenshots/video, provider/Apple sandbox, licenses
- Evidence root: immutable/reproducible repository or artifact-store path, retention, hash and access scope (chat links alone are invalid)

## Findings

| Severity | File/contract/journey | Finding | Required fix | Resolution commit/evidence |
|---|---|---|---|---|
| P0/P1/P2 | | | | |

## Verification rerun

Record the exact command/journey, timestamp, result, and artifact path after fixes. A previous run or agent summary is not fresh evidence.

For store/blob/queue/backup/privacy canary checks, record the query or script version, environment, time window, positive control, negative canary IDs/hashes, result artifact hash and retention. Redact secrets and personal data; do not paste raw production payloads into the review.

## Verdict

- `APPROVE` only when the reviewed scope matches acceptance criteria and has no unresolved P0/P1.
- `CLEAR` only when no known architecture/security/privacy/reuse blocker remains in the reviewed scope.
- Otherwise use `REQUEST_CHANGES` and list the blocking finding IDs.
