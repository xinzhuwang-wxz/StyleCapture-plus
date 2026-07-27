# Design Merge — Missing Capabilities ExecPlan

> Keep this plan current as behavior, evidence, and product decisions change.

**Branch:** `codex/design-merge-gaps`
**Status:** Stages 1–5 implemented and locally green. Evidence run and PR pending.

## Why this exists

A new mobile design (Claude Design project `StyleCapture Mobile.dc.html`) was to be
merged with main's frontend as a union. Auditing main file by file showed main already
implements most of that design — Feed with lasso capture, wardrobe by look and by item,
outfit detail, AI recommendations, analysis, and the pixel world (which the design does
not contain at all).

Four capabilities were genuinely missing. This plan covers only those four. The visual
restyle is deliberately **not** in scope; it is a separate round, and this round avoids
touching existing class names and visible copy so the ~18 existing test files keep
passing.

## Observable outcome

On a 390×844 viewport a user can:

1. Record body metrics — nickname, age, height, weight, bust/waist/hip, body shape —
   on a wheel picker that is also keyboard- and screen-reader-operable.
2. Manage up to six reference photos, mark one as the try-on reference, and delete
   others, with the album surviving a refresh.
3. Build a combo from wardrobe items by long-pressing and dragging, or equivalently by
   pressing a plain button, then save the combo as a new outfit.
4. Open a share sheet for a look's pixel cover, hand the image to the system share
   sheet, save it, or copy a real link.

## Decisions

- **Body metrics and photos are local-only.** No FastAPI change, no migration, no API
  contract regeneration. The key convention follows main's existing
  `stylecapture:<feature>:v<n>` (see `ProfileScreen.tsx`'s `PIXEL_TRIAL_STORAGE_KEY`).
- **Reads never throw.** `src/storage/localStore.ts` falls back to defaults on corrupt
  or version-mismatched data, and on private-mode `localStorage` access throwing.
  Writes report quota failure visibly rather than silently dropping data.
- **Photos are downscaled before storage.** Six originals cannot fit in
  `localStorage`; `media/downscaleImage.ts` fits each within 720px and re-encodes at
  JPEG q0.82 (~18KB each). `photoStorage.ts` accepts only `data:image/` URLs — a remote
  URL would turn a private photo into a network request.
- **Drag is an enhancement, never the only path.** Every item card carries a plain
  `加入组合` button doing the same thing, so keyboard and screen-reader users are not
  dependent on a pointer gesture. `pressGesture.ts` is a pure state machine so the
  tap / long-press / list-scroll discrimination is unit-testable without a DOM.
- **Combo saving reuses existing APIs.** `planOutfits({ mustIncludeItemIds })` followed
  by `saveOutfitPlan` — no new endpoint. Duplicate-category checking delegates to
  main's existing `features/wardrobe/comboRules.ts` rather than a second rule set.
- **The share sheet does not overclaim.** An H5 cannot publish to Douyin on a user's
  behalf, so the button says `分享到…` and hands off to the system share sheet. No QR
  code is drawn — a code that scans to nothing is worse than none — so the offer is
  `复制链接看同款`, which yields a link that actually opens.

## Scope note: the pixel world

An earlier plan stage called for replaying two unmerged commits (three venue characters
plus a guest roster; unified sprite sizing plus video group photos) onto main by hand.
That turned out to be unnecessary: PR #36 carried exactly those commits and was merged
into main at 2026-07-27T02:15:31Z (merge commit `8c0e506`). Main verifiably contains
all of it — seven personas, seven pose sets, the cast picker, `recordClip`, the sprite
scripts — with zero `gifenc` references remaining. The hand replay was performed against
a stale base before this was discovered and has been dropped from the delivery branch;
it survives on `codex/design-merge` at `3c1b89a` for reference.

## Verification

Per stage: `pnpm test`, `pnpm typecheck`, `pnpm build`.

Whole-journey evidence at 390×844, including failure and recovery states, not only the
happy path. Local persistence is verified separately: write → refresh → read back, and
deliberately corrupting the stored value must still leave the app bootable.

## Known gaps

- `tests/app.test.tsx` → "removes a restored processing card when its backend job no
  longer exists" fails intermittently under full parallel load (cannot find
  `正在理解这件衣服`). It passes in isolation and on re-run; the cause is timing, and it
  predates this branch. Not worked around by weakening the assertion.
- The delivery branch is based on `b1b08ab`; main has since advanced to `f7abb615`.
  Mergeability must be checked on the PR rather than assumed.
