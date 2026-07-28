# Feed runtime flake report

## Change

- Replaced the fixed 710 ms helper sleep in `drawAndConfirm` with awaited visible button lookup via `screen.findByRole`.
- Preserved the intent-specific accessible names, click flow, product quiet-window policy, and existing assertions.

## Verification

- `pnpm --dir apps/h5 exec vitest run tests/feed-runtime.test.tsx` -> passed.
  - Test Files: 1 passed (1)
  - Tests: 12 passed (12)
  - Duration: 4.38s

## Self-review

- Scope stayed within `apps/h5/tests/feed-runtime.test.tsx` and this report.
- The helper no longer assumes the 700 ms quiet window plus React scheduling completes inside a 10 ms real-time slack.
- Existing intent-dependent accessible names, click flow, product code, timeouts, and assertions were preserved.
