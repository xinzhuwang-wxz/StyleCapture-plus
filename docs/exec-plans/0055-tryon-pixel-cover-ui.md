# Try-on to pixel cover UI

## Goal

Turn the existing Look-detail try-on entry into one continuous user journey: the
compact `查看效果` card opens the already-shared profile-photo picker, the
completed try-on appears in the same detail page, and that result can start a
background pixel-card task. Generated pixel people are collected in `我的` and can
be selected as the corresponding Look's wardrobe cover.

This slice does not change the try-on provider. It does extend the render request
contract so a pixel card started from a completed try-on is traceably generated
from that exact try-on artifact.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Profile-photo selection | `TryOnPhotoSheet`, shared `PhotoAlbum`, existing App callbacks | Direct reuse | The requested photo selection and upload flow already exists and shares data with `我的形象照`; only its entry point needed to move. | Repository HEAD `3c51cad`, project license |
| Try-on and pixel jobs | Existing `RenderArtifact` list and `wardrobeApi.createRender` | Direct reuse | Keeps the current API contract and background polling instead of introducing a frontend-only job model. | Repository HEAD `3c51cad`, project license |
| Mobile bottom sheet | Existing sheet handle, phone-frame overlay, Motion transitions | Adapted reuse | Reuses established interaction and visual tokens for the collapsible pixel task surface. | Repository HEAD `3c51cad`, project license |
| Pixel-cover persistence | Existing successful `pixel_cover` artifacts and Look-card cover map | Adapted reuse | Adds an explicit per-Look local choice while the backend cover-selection contract does not yet exist. | Repository HEAD `3c51cad`, project license |

## Decisions

1. `查看效果` is the single try-on entry. With no successful try-on it opens the
   existing shared image picker; with a result it scrolls to that result.
2. The old parallel `真人试穿 / 像素封面` studio tabs and the lower
   `拍照或上传全身照` button are removed.
3. Pixel generation starts only from the completed try-on card in this UI. Its task
   sheet can collapse to a floating orb and continues to reflect backend polling.
4. A newly generated pixel artifact is not automatically used as the wardrobe cover.
   The user explicitly chooses `设为像素封面`; legacy artifacts remain selected when
   no explicit choice has been saved.
5. `我的` replaces the standalone pixel trial lab with a gallery of successful,
   Look-linked pixel cards. Profile-photo management remains unchanged.
6. Pixel cards started from a try-on keep that completed try-on artifact as their
   explicit and validated source. Other automatic pixel jobs keep the legacy source.

## Verification plan

Pixel generation started from the try-on result sends that successful try-on's
`source_artifact_id`. The backend validates same owner, same Look, successful
status, and `try_on` kind before using its output as the sole content image.
Automatic pixel generation elsewhere keeps the legacy original-Look/collage path.

- Update Look-detail tests for the moved entry and continuous flow.
- Replace the obsolete profile pixel-trial test with a Look-linked gallery test.
- Run H5 typecheck, focused behavior tests, production build, and mobile browser
  inspection on an isolated local port.

## Verification results

- `tsc -b apps/h5/tsconfig.json --noEmit` passed.
- `vitest run tests/look-wardrobe.test.tsx` passed: 27 tests.
- `vitest run tests/app.test.tsx` passed: 30 tests.
- Full H5 suite passed all changed-feature tests; one pre-existing Feed timing test
  failed under full parallel load and passed immediately when rerun in isolation.
- `tsc -b && vite build` passed: 547 modules transformed.
- Pixel-source follow-up: focused H5 tests passed (27 tests), H5 typecheck passed,
  backend render processing tests passed (14 tests), and Ruff passed. The HTTP test
  module cannot collect directly on Windows because the existing local object store
  imports Unix-only `fcntl`; its request contract is still represented in the
  generated OpenAPI contract.
- Asset-selection follow-up: the profile gallery now lists every successful pixel
  artifact (including multiple try-on-derived cards for the same Look), while the
  wardrobe grid resolves the exact artifact id selected by the user instead of
  falling back to the collage placeholder.
- Completed item flat-lays are no longer sent through the frontend ensure call when
  a try-on render is active. The ensure endpoint remains idempotent for genuinely
  missing assets, but successful assets now trigger no redundant request at all.
- Final post-rebase verification passed: 59 H5 tests across `app.test.tsx` and
  `look-wardrobe.test.tsx`, 16 backend render-processing tests, Ruff, H5 typecheck,
  and the production Vite build.

## Surprises & discoveries

- A successful older pixel artifact may coexist with a newer running artifact. The
  task sheet must show the running state instead of presenting the older result as
  newly completed.
- The current backend has no persisted "selected Look cover artifact" field, so the
  explicit selection is local-device state in this slice.
- Before the source contract was added, every `pixel_cover` request implicitly created
  or reused a collage source, so the backend had no way to know which try-on result the
  user had clicked.

## Progress

- [x] Move the shared try-on picker entry to `查看效果`.
- [x] Add the inline completed try-on result and actions.
- [x] Add collapsible pixel-card background task UI.
- [x] Replace profile pixel lab with the Look-linked pixel gallery.
- [x] Persist and display the exact selected pixel artifact as the wardrobe cover.
- [x] Show every successful Look-linked pixel artifact in the profile gallery.
- [x] Avoid re-ensuring completed item flat-lays during try-on activity.
- [x] Update behavior tests and pass production build.
- [ ] Complete mobile browser visual review on the isolated local port.
