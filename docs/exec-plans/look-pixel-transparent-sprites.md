# Look pixel cards and transparent world sprites

## Observable outcome

Every successful Look pixel-cover render keeps its illustrated wardrobe card and, in
parallel, stores a transparent PNG character sprite. The pixel world consumes the
transparent sprite; existing cards without one are backfilled when their render list
is read, with the browser cutout retained only as compatibility fallback.

## Reuse audit

`pixel card cutout -> PR #54 PillowPixelSpriteExtractor at 1793f1d -> adapted reuse -> deterministic, already tested against the authored card composition and adds no hosted provider -> repository code, project license`

`world character loading -> existing spriteLoader canvas cutout -> retained fallback -> protects old or failed assets but is no longer the primary stored artifact`

## Plan

- [x] Persist optional sprite metadata on `render_artifacts` with a migration.
- [x] Extract and store a PNG after successful pixel-cover generation.
- [x] Expose sprite URL and finite status in the render API.
- [x] Backfill successful historical cards once and stop retrying failed extraction.
- [x] Prefer the sprite in the pixel-world catalogue without removing its backdrop again.
- [x] Regenerate the H5 OpenAPI contract and add focused backend/frontend tests.

## Decision log

- The card and sprite belong to the same render artifact because they are two
  presentations of one generated Look, not separate user-owned wardrobe assets.
- A sprite extraction failure does not invalidate the card. It is recorded in the
  private provider trace and the frontend keeps its existing runtime cutout fallback.
- Background removal remains deterministic Pillow processing; no Doubao call or user
  photo leaves the existing generation boundary.

## Surprises and discoveries

- PR #54 was closed without merge and only connected a profile PixelTrial sprite. It
  did not associate transparent sprites with every Look pixel-cover render.
- The `我今晚的 LOOK` rail renders the same source URL as the world; supplying the
  server sprite fixes both without a separate thumbnail pipeline.

## Verification

- Backend processing/domain/cutout: 20 tests passed.
- Render repository migration/persistence: 4 tests passed.
- H5 community/app/wardrobe: 70 tests passed.
- H5 TypeScript typecheck passed.
- Ruff passed; mypy is rerun after the final Literal typing correction.
