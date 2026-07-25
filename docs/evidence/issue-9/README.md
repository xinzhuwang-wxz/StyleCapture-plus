# Issue #9 — Pixel Dance Community Evidence

Viewport: 390 × 844 mobile browser.
Journey: open the H5 Community tab, tap the central dance floor, send `闪闪`, inspect
the explicitly non-human resident `紫丁香`, create a PNG share card, and simulate a
browser Canvas export failure to verify retry recovery.

| Evidence | State |
| --- | --- |
| `01-community-initial.png` | Community tab and initial ballroom scene |
| `02-community-dancing.png` | A tap on the dance floor moves the avatar and starts the dance loop |
| `03-community-resident.png` | Resident drawer only exposes `场景居民` and public style tags |
| `04-community-share-ready.png` | Share-card download succeeds |
| `05-community-share-failure.png` | Browser export failure shows a retryable action |
| `06-community-share-recovered.png` | Retrying after the simulated export failure succeeds |
| `07-community-share-card.png` | Downloaded card includes the current demo avatar, dance state, and reaction |

Fresh browser evidence: `STYLECAPTURE_E2E_BASE_URL=http://127.0.0.1:5174 pnpm exec
playwright test e2e/community-ballroom.spec.ts` produced 2 passing tests.

Visual verdict:

```json
{
  "score": 95,
  "verdict": "pass",
  "category_match": true,
  "differences": [
    "The community view intentionally uses a dark night-scene surface instead of the wardrobe's light paper surface.",
    "The third navigation item is denser than the original two-item navigation but remains readable at the approved mobile viewport."
  ],
  "suggestions": [
    "Keep future community scenes on the same purple-pink palette and retain the labelled resident treatment.",
    "Reassess navigation density before adding a fourth primary destination."
  ],
  "reasoning": "The mobile scene retains the established StyleCapture pixel-purple identity while making movement, dance, public-only resident information, share-state feedback, and the downloaded avatar card visually legible."
}
```
