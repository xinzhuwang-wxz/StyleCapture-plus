# Wardrobe status and sheet UI polish

## Goal

Make the wardrobe's provenance and organization state readable, remove redundant
item-detail metadata, require an explicit confirmation before users change item
category or ownership, and align the capture/share sheets with the approved mobile
references.
Also align the AI recommendation and profile headers with the same calm mobile
visual hierarchy without changing recommendation behavior.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason |
| --- | --- | --- | --- |
| Item update persistence | `wardrobeApi.updateItem`, `PATCH /v1/items/{item_id}` | Direct reuse | It already persists ownership and attribute corrections through the typed Product API. |
| Destructive confirmation pattern | `DeleteAssetDialog.tsx` | Adapted reuse | The existing accessible dialog pattern provides focus and busy-state behavior; this slice adds a non-destructive change confirmation variant. |
| Mobile overlays | `CaptureSheet.tsx`, `ShareCardSheet.tsx`, existing portal to `.pixel-screen` | Adapted reuse | Keeps overlays inside the phone frame while making their layout match the approved references. |

## Decisions

1. Look card metadata is `source · organization state`, where source is derived from the persisted Look source and organization state is derived from the persisted Look state plus in-flight render artifacts.
2. Item cards show ownership plus `已整理` only when ready; every non-ready state is represented as `正在整理` rather than exposing internal pipeline labels.
3. A category/ownership choice is applied only after confirmation. Cancelling leaves both local state and the backend unchanged.
4. The share sheet stays honest: it invokes the platform share surface, rather than claiming an automatic Douyin publish.
5. Both wardrobe views expose the same compact filter control. Look filters use the
   persisted source values behind the visible labels: local upload, inspiration
   collection, and AI recommendation.
6. The AI screen owns only its recommendation content; the shared app header shows
   `AI推荐 / 今天你想穿什么？`, while the profile header stacks its subtitle under
   `我的` like the wardrobe screen.
7. AI chat presentation becomes quieter: pale user messages, shadowless assistant
   messages, squarer option chips, and a single-layer embedded composer.
8. AI action accents reuse that same pale message color: the match score and save
   action are flat rather than embossed, while the composer send control is circular.

## Verification plan

- Update behavior tests for card labels and item change confirmation.
- Run H5 typecheck and focused component tests.
- Exercise capture and share sheets at mobile viewport and capture screenshots.

## Verification results

- `pnpm.cmd --filter @stylecapture/h5 typecheck` passed.
- `pnpm.cmd --filter @stylecapture/h5 test` passed: 32 files, 260 tests.
- `pnpm.cmd --filter @stylecapture/h5 build` passed.
- Mobile viewport inspection confirmed the capture confirmation fills the phone frame
  after its entry animation and the share sheet remains a centered, self-contained
  modal over the detail screen.
- A second mobile viewport pass confirmed the AI composer is a single visual layer,
  the recommendation header no longer repeats itself, and the profile subtitle sits
  directly beneath `我的` without overflow.

## Progress

- [x] Update card/detail information hierarchy.
- [x] Add item-change confirmation UI.
- [x] Rework capture and share sheets.
- [x] Polish AI recommendation and profile title hierarchy.
- [x] Complete browser and visual verification.
