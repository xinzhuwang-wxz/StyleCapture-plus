# Issue #9 — Pixel Runway Ball evidence

Viewport: 390 × 844 mobile Chromium.

The standalone journey previews a local Look backstage, requires an explicit runway
publish action, animates the Look into the spotlight, unlocks a dance mode, browses and
collects curated pixel Looks, records a style reaction, and downloads a share card.

Run locally:

```bash
pnpm --filter @stylecapture/h5 dev:party
```

Direct URL: `http://127.0.0.1:5175/?demo=style-party`

| Evidence | Observable state |
| --- | --- |
| `01-pixel-runway-ball.png` | Pixel ballroom, runway, the user's pixel character and three curated Look guests |
| `02-browse-and-collect.png` | A curated Look selected and collected locally |
| `03-runway-in-motion.png` | Explicitly published local Look moving from backstage to center stage |
| `04-dance-mode.png` | Dance mode unlocked after runway completion |
| `05-pixel-runway-share-card.png` | Downloaded PNG generated from the selected visible Look |
| `06-share-ready.png` | Successful download feedback |
| `07-recovery-states.png` | Invalid upload and Canvas export recovery states |

Scene floor, runway, sofa, plant, and painting sprites are reused from
`pixel-agents-hq/pixel-agents@f6cdd2d37e203f4df8a7341e93b35df6d47b5fb5`
under MIT. The frame loop is a small attributed adaptation of the same project. The
StyleCapture pixel Looks remain first-party/user-provided assets.

The seed Looks are labelled `精选示例 · 非真人`. This validation does not claim live
users, presence, persistent reactions, or persistent collections.

Fresh verification:

- `pnpm test`: 10 files / 47 tests passed.
- `pnpm typecheck`: passed.
- `pnpm build`: production Vite build passed.
- Mobile Chromium: 2 complete journeys passed, including transparent walking guests,
  explicit publish, runway, dance, collection, reaction, download, invalid upload, and
  export retry.
- Visual Verdict: 95/100 against the supplied full-body fashion-pixel reference.
