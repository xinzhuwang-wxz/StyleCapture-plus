# Task 3 pause checkpoint — 2026-07-29

## Pause state

- User explicitly requested a pause after asking for a current-state summary.
- The `journey` hourly automation is `PAUSED`.
- All native subagents are completed or interrupted; no implementation or review agent remains running.
- Xcode, Docker, and the iPhone Simulator were not started for this candidate. The available simulator is `StyleCapture-iPhone-17` (`F899E4E4-D274-4D19-B810-5D62384E0094`) and remains shut down.
- The aggregate Goal remains active. This is a recoverable checkpoint, not a completion or blocked claim.

## Frozen baseline and hosted evidence

- Branch: `codex/stylecapture-journey`
- Baseline before this checkpoint: `375777f983725056dfbfe96eb03c0881d038dfd4`, equal to `origin/codex/stylecapture-journey` when work resumed.
- Hosted run: `30428193293`
  - `product`: GREEN, including Python/PostgreSQL behavior, generated API contract, mobile/H5, Compose, and backend image validation.
  - `ios`: FAILED only in `Test iOS foundation` on two compile errors in `KeychainTokenStoreTests.swift`:
    - missing `from:` argument label;
    - ambiguous `.accountDeletionPending` enum inference.

## Implemented in the paused worktree

1. Fixed both known `KeychainTokenStoreTests` compile errors without weakening assertions.
2. Removed the stable Apple user identifier from `AuthenticatedAccount` and observable TCA auth state. The identifier remains in secure token storage, and credential-state lookup moved behind `AuthClient`.
3. Fixed Apple provider revocation recovery:
   - expired `attempted` leases are reclaimable while active leases are not;
   - a provider grant returned after account deletion wins the exchange/bind race is encrypted and recorded for revocation;
   - the first implementation raised inside the SQL transaction and would have rolled back the outbox record; this was caught during integration and corrected so the transaction commits before `SubjectDeletedError` is returned;
   - SQL regression assertions cover durable auth-code/grant creation, absence of identity/session/alias creation, later revocation, and ciphertext wipe.
4. Began a `#if DEBUG` TCA dependency harness for deterministic Simulator auth/deletion/recovery UI scenarios and expanded UI tests. This harness was interrupted at the pause boundary and is not accepted evidence.

## Fresh lightweight verification

- `git diff --check`: PASS.
- `xcrun swiftc -parse` across all changed iOS source/test files, including the interrupted harness: PASS. This proves syntax only, not type-check/build/runtime behavior.
- Backend in-memory account suite: `14 passed`.
- Targeted backend Ruff: PASS.
- Targeted backend mypy: PASS.
- Resource state before pause: no thermal or performance warning, memory free approximately 54%, disk approximately 81 GiB free. The largest CPU consumers were external GUI processes, not Xcode/Simulator/Docker jobs from this task.

## Open findings and evidence gaps

1. The strengthened SQL tests have not run against real PostgreSQL since Docker was intentionally not started. Hosted CI must execute them.
2. The current iOS worktree has not been type-checked or tested by Xcode. Hosted iOS CI has not been rerun after the compile fixes.
3. `storedAppleCredentialIsValid` currently returns `true` if the second secure-store read no longer contains an authenticated session. On resume, review this restore/credential-check TOCTOU behavior and normally fail closed (`false`) for a missing/deletion-pending session, with a regression test.
4. The interrupted Simulator harness needs completion and review before use:
   - explicitly prove it is excluded from Release in `project.yml`/generated project;
   - replace or justify its `UserDefaults` deletion marker against the existing secure public auth seam;
   - remove the long suspended sleep in favor of deterministic test control;
   - prove the live Apple scenario displays the real SIWA system sheet rather than only the app's `signingIn` state;
   - run type-check/UI tests and label all scripted states as DEBUG Simulator evidence, never production behavior.
5. The focused code/security re-review was interrupted by the pause and must be restarted against the eventual frozen candidate.
6. No fresh matching-HEAD Simulator screenshots, recording, or visual-verdict score exist yet.

## Exact resume order

1. Inspect this checkpoint diff; close the fail-closed auth restore finding.
2. Finish and independently review the DEBUG Simulator harness without changing production reducer ownership.
3. Run lightweight checks, form a Lore checkpoint, push, and dispatch hosted product+iOS CI.
4. After hosted GREEN, resource-preflight and boot exactly one `StyleCapture-iPhone-17` Simulator with build concurrency capped at two. Exercise real taps for signed-out, live SIWA sheet, failure/retry, deletion processing, relaunch reconciliation, and cleanup recovery; save and surface fresh screenshots/video; shut the simulator down afterward.
5. Run the Task 3 milestone-wide spec, architecture, code/security, privacy, reuse, and UX/visual reviews; fix P0/P1 findings and reverify as one batch.
6. Only after Task 3 closes, begin the already-mapped Task 4 garment-import vertical slice.
