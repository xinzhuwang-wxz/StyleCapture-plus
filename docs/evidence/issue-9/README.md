# Issue #9 — Pixel Style Party evidence

Viewport: 390 × 844 mobile Chromium.

The journey starts from the secondary experiment entry in Digital Wardrobe, then
browses a theme Look, collects it, publishes the user's pixel Look, leaves a
style-specific reaction, generates a PNG share card, and verifies export recovery.

| Evidence | Observable state |
| --- | --- |
| `01-style-party-theme.png` | `花房晚宴` theme, value proposition, truthful demo label, and complete pixel Look |
| `02-browse-pixel-looks.png` | Another curated pixel Look selected on the same stage |
| `03-collect-inspiration.png` | Selected Look collected locally with explicit feedback |
| `04-publish-my-look.png` | The user's actual supplied pixel avatar source on stage |
| `05-style-reaction.png` | `层次感` response selected without fabricated counts |
| `06-share-ready.png` | Download completion feedback |
| `07-style-party-share-card.png` | Downloaded card drawn from the currently visible pixel Look |
| `08-share-retry.png` | Browser export failure with a visible retry action |

The seed Looks come from the user-provided project asset pack and are labelled
`精选示例 · 非真人`. This validation does not claim a live community, real users,
persistent likes, or persistent collections.

Fresh verification:

- `pnpm --filter @stylecapture/h5 test`: 10 files / 42 tests passed.
- `pnpm --filter @stylecapture/h5 typecheck`: passed.
- `pnpm --filter @stylecapture/h5 build`: production Vite build passed.
- `STYLECAPTURE_E2E_BASE_URL=http://127.0.0.1:5175 pnpm exec playwright test
  e2e/community-ballroom.spec.ts`: 2 mobile journeys passed.

Visual verdict against the supplied fashion-pixel reference:

```json
{
  "score": 94,
  "verdict": "pass",
  "category_match": true,
  "differences": [
    "The reference is a compact four-card community grid while the demo intentionally gives one selected Look a full theme-stage hero",
    "The demo removes reference-like heart counts because no live community data exists"
  ],
  "suggestions": [
    "Keep the complete fashion-paper-doll silhouette and pastel card treatment when live UGC replaces the curated seeds",
    "Connect publish, collect, reaction, and share callbacks to real community services before showing persistent counts"
  ],
  "reasoning": "The redesign now reads as the same fashion-pixel product category, with materially stronger scene identity and a coherent UGC-to-share journey. The remaining differences are intentional product-truthfulness and hierarchy decisions rather than visual defects."
}
```
