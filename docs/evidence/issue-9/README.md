# Issue #9 — Pixel Dance Community Evidence

Viewport: 390 × 844 mobile browser.
Journey: open the H5 Community tab, tap the central dance floor, send `闪闪`, inspect
the explicitly non-human resident `紫丁香`, enter the runway with `轮到我上台`, create
a PNG share card, and simulate a browser Canvas export failure to verify retry recovery.

| Evidence | State |
| --- | --- |
| `01-community-initial.png` | Community tab and initial ballroom scene, with ten full fashion-pixel characters |
| `02-community-dancing.png` | A tap on the dance floor moves the avatar and starts the dance loop |
| `03-community-resident.png` | Resident drawer only exposes `场景居民` and public style tags |
| `04-community-share-ready.png` | Share-card download succeeds |
| `05-community-share-failure.png` | Browser export failure shows a retryable action |
| `06-community-share-recovered.png` | Retrying after the simulated export failure succeeds |
| `07-community-share-card.png` | Downloaded card includes the current fashion-pixel avatar, dance state, runway state, and reaction |
| `08-community-runway.png` | Runway state after `轮到我上台`, with the status live region showing `正在走秀` |

Fresh browser evidence: `STYLECAPTURE_E2E_BASE_URL=http://127.0.0.1:5175 pnpm exec
playwright test e2e/community-ballroom.spec.ts` produced 2 passing tests.

Fresh H5 verification: `pnpm --filter @stylecapture/h5 test && pnpm --filter
@stylecapture/h5 typecheck && pnpm --filter @stylecapture/h5 build` produced 9
passing Vitest files / 37 tests, a clean TypeScript check, and a successful production
Vite build.

RenderArtifact handoff boundary: this evidence still uses the labelled `Demo 像素形象`
avatar source. The Community UI accepts a future public Look RenderArtifact once Issue
#3/#5 provides it, but this Issue #9 journey does not expose original reference images
or private Item media in the browser, screenshots, or downloaded card.

Visual verdict:

```json
{
  "score": 91,
  "verdict": "pass",
  "category_match": true,
  "differences": [
    "The reference is a light product poster while this surface intentionally remains an interactive dark runway.",
    "The scene characters are purpose-built CSS pixel dolls instead of the reference's more detailed illustrated sprites."
  ],
  "suggestions": [
    "Keep the distinct hair, outfit, shoes, and accessory treatment when expanding the resident catalog.",
    "Use public Look RenderArtifacts for the next fidelity step rather than exposing original reference images."
  ],
  "reasoning": "The mobile scene reads as a fashion-pixel runway rather than a generic block-person map: every visible role has a distinct paper-doll silhouette and palette, while movement, runway state, public-only resident information, share feedback, and the downloaded card remain legible."
}
```
