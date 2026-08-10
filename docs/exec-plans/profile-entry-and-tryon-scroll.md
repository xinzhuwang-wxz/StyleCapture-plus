# Profile secondary navigation and stable try-on detail

## Goal

Make the profile and combo secondary pages feel like true subpages, move body-data management to the profile header, flatten the action styling, and stop a completed try-on task from moving the user's current scroll position.

## Observable outcomes

- The profile header action says “管理个人数据” and opens body-data management.
- The profile summary card shows plain item/look counts only; body-data and pixel-person shortcut copy are removed.
- Photo management and combo wardrobe no longer repeat their parent-page headers.
- Photo/combo actions use restrained outlined/pale controls without embossed shadows or saturated yellow/purple fills.
- Completing a try-on render does not automatically scroll or refocus the detail sheet. Explicit “查看效果” navigation remains.
- The existing “真人试穿暂不可用” behavior is intentionally unchanged.
- Chat history uses neutral “AI” wording without “闺蜜”.
- Bust, waist, hip, and body shape are genuinely optional local fields; each measurement can be filled or cleared independently, and an active body shape can be deselected.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Body-data editor | `BodyProfileSheet`, existing profile state | Direct reuse | Same data contract and save path; only the entry point changes | repository `45d4ea5`, project license |
| Profile secondary pages | Existing `PhotoManagerSheet` conditional rendering | Adapted reuse | Lift subpage selection so the parent header can react without creating another router | repository `45d4ea5`, project license |
| Combo secondary page | Existing `ComboDetailSheet` | Adapted reuse | Preserve save/try-on behavior; expose open state to the parent | repository `45d4ea5`, project license |
| Action controls | Existing `PixelButton` markup | Adapted reuse | CSS overrides are sufficient; no new component system needed | repository `45d4ea5`, project license |

## Implementation plan

- [x] Add behavior tests for profile navigation and stable try-on completion.
- [x] Lift profile/combo secondary-page state to `App` and hide parent headers while open.
- [x] Simplify the profile summary card and flatten photo/combo action styling.
- [x] Remove automatic completion scrolling and prevent focus management from moving the viewport.
- [x] Run focused tests, type checks, build, and mobile visual verification.
- [x] Make measurements/body shape optional in both local storage and the editor, then verify the new interaction.

## Decision log

- 2026-08-10: Keep the explicit “查看效果” scroll action; remove only automatic movement after background completion.
- 2026-08-10: Do not change try-on failure/unavailable behavior in this slice, per user direction.
- 2026-08-10: Keep the profile title/summary in the parent header and replace only its right-side Feed action with “管理个人数据”.
- 2026-08-10: Represent unknown measurements and body shape as `null` rather than silently inventing defaults; keep the existing v1 local-storage parser backward compatible with previously saved numeric values.

## Surprises & discoveries

- The detail focus effect was coupled to transient modal state and could refocus the top close button on unrelated updates. It will be separated from Escape-key handling and use `preventScroll`.
- A first visual pass exposed that the profile action had replaced the title block instead of the right-side Feed action; the header structure was corrected before handoff.

## Verification evidence

- `vitest run tests/app.test.tsx tests/look-wardrobe.test.tsx`: 2 files, 66 tests passed.
- `tsc -b`: passed.
- `vite build`: passed; 547 modules transformed.
- `vitest run tests/body-profile.test.ts`: 8 tests passed.
- `vitest run tests/body-profile-sheet.test.tsx`: 9 tests passed.
- `vitest run tests/chat-history-sheet.test.tsx`: 2 tests passed.
- Headless mobile viewport (589 × 879): profile overview and body-data subpage verified. The overview retains “我的” with a single “管理个人数据” action; the body subpage contains no parent header.
- The broader H5 suite was also sampled. All unrelated suites passed except six existing/timing-sensitive `feed-runtime.test.tsx` cases when run in the full parallel batch; this slice does not modify Feed runtime files, and the directly affected suites pass cleanly in isolation.
