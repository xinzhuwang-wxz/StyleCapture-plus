# Pixel Style Party Demo ExecPlan

> Keep this plan current as behavior, evidence, and product decisions change.

**Issue:** [#9](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/9)
**PR:** [#10](https://github.com/xinzhuwang-wxz/StyleCapture-plus/pull/10)
**Status:** Independent concept validation, rebuilt as a walkable pixel world.
This branch may be closed without merging.

## Observable outcome

A mobile-first pixel world you can walk around in. A user opens a standalone local
URL, taps to move, walks up to preset guests and has a real back-and-forth with
them, changes their whole Look without leaving the page, walks the runway (or just
steps onto the stage), watches the room gather and applaud with floating pixel
reactions, and takes away a group photo — either a still card or an animated one
whose caption holds still while the scene keeps moving. Three locations, each with
its own occasion.

The experiment tests one product hypothesis:

`theme prompt → preview pixel Look → runway ritual → dance/social signal → collect → share → new participation`

It does not add a live community backend, primary navigation destination, real-time
  presence, or a general game framework.

## Product and interaction decisions

- **Scene:** `花房夜宴`, a pixel greenhouse runway and dance floor built from directly
  reused Pixel Agents tiles/furniture plus a thin adapted Canvas loop.
- **UGC:** upload is a backstage preview; `上台走秀` is the explicit publish action and
  calls a replaceable
  `onPublishLook` boundary with the visible pixel artifact. The standalone demo also
  accepts a local PNG/JPG/WebP, keeps it in a revocable object URL, and never uploads it.
- **Participation ritual:** the avatar walks from backstage to the central pose point.
  `加入舞会` unlocks only after the runway completes and `换一个舞步` changes the
  animated pose.
- **Social:** responses describe why a Look works (`配色好会`, `层次感`,
  `想抄作业`) instead of fabricated likes or follower counts.
- **Retention:** curated Looks can be collected locally as styling inspiration through
  a replaceable `onSaveInspiration` boundary.
- **Distribution:** the current visible pixel image becomes a downloadable share card;
  loading, duplicate taps, Canvas failure, and retry are explicit.
- **Independence:** the wardrobe contains a secondary experiment card. The confirmed
  Feed / Wardrobe primary navigation is unchanged, and the feature can be removed as
  one overlay module. `?demo=style-party` opens it directly without starting wardrobe
  queries or requiring the API.
- **Truthfulness:** supplied examples are labelled `精选示例 · 非真人`; local state is
  labelled `非实时社区`.

## Reuse audit

| Capability | Candidate | Decision | Reason | Source / commit / license |
| --- | --- | --- | --- | --- |
| H5 shell, interaction, motion | Existing React/Vite/Motion application | Direct reuse | Preserves one deployable H5 and avoids a second runtime | This repository at base `7747783`; React, Vite and Motion are MIT |
| Pixel Look presentation | User-provided `素材库.zip` (`像素图1-3.png`) | Direct reuse of the three pixel-only examples | They match the product's complete fashion-pixel silhouette and require no new avatar engine | User-provided project asset, 2026-07-25; hashes recorded in `apps/h5/public/assets/community/README.md` |
| Pixel scene tiles and furniture | Pixel Agents office assets | Direct reuse | Supplies a coherent real pixel world without redrawing a fake CSS environment | `pixel-agents-hq/pixel-agents@f6cdd2d37e203f4df8a7341e93b35df6d47b5fb5`; MIT; copied files and license under `public/assets/community/pixel-agents/` |
| Canvas frame loop / character scene state | Pixel Agents game loop and character state machine | Adapted reuse | The clamped `requestAnimationFrame` loop and explicit runway/spotlight/dance states deliver real movement without importing its VS Code host, terminal tracking, editor, or pathfinding subsystems | Same pinned Pixel Agents commit; MIT; attribution in `pixelSceneEngine.ts` |
| Multiplayer / live presence | Agent Office; Colyseus; RPGJS | Rejected for this validation | A server room and general game framework do not improve the local UGC/share hypothesis and would create a new runtime boundary | Inspected in the earlier Issue #9 audit; MIT candidates |
| Share export | Browser Canvas 2D | Direct reuse | Local, dependency-free export of the same public pixel image visible on stage | Browser platform API |

## Acceptance checklist

- [x] Secondary wardrobe entry opens an isolated full-screen experience.
- [x] `?demo=style-party` opens the complete experience without backend data.
- [x] The first viewport explains the theme and value proposition.
- [x] Three complete pixel-fashion examples can be browsed and are labelled as examples.
- [x] The supplied `avatarSource` is the same image shown on stage and exported.
- [x] A local PNG/JPG/WebP can replace the demo avatar and is revoked when replaced or
  when the experience closes.
- [x] Upload remains backstage until the user explicitly publishes with `上台走秀`.
- [x] A user can complete the runway, unlock dance mode, switch dance steps, collect a
  curated Look, and leave a style reaction.
- [x] The scene directly reuses pinned MIT Pixel Agents assets and an adapted game loop,
  with local attribution and license.
- [x] Integration callbacks exist for publish, collect, react, and share.
- [x] No fabricated residents, likes, presence, or community counts are shown.
- [x] Share generation waits for image loading, prevents duplicate export, fails
  visibly, and can be retried.
- [x] Fresh unit, typecheck, build, mobile browser, share-card, and visual evidence pass.
- [x] Commit, push, and update PR #10 without merging it.

## Progress

- [x] 2026-07-25: Merged current `main` into the isolated PR branch and resolved the H5
  navigation conflict without touching the user's primary checkout.
- [x] 2026-07-25: Removed the old map, movement, dance, resident drawer, CSS dolls, and
  primary Community tab.
- [x] 2026-07-25: Implemented the `花房晚宴` theme stage, curated Look rail, own-Look
  entrance, style reactions, local collection, and share-card states.
- [x] 2026-07-25: Added feature-local styles, real `avatarSource` rendering, integration
  callbacks, focused reducer/component tests, and the user-supplied pixel assets.
- [x] 2026-07-25: Completed 10-file / 42-test H5 regression, TypeScript check,
  production build, two 390×844 Chromium journeys, downloaded-card inspection, and a
  94/100 visual verdict.
- [x] 2026-07-25: Committed the redesign as `edd3b89`, pushed the existing PR branch,
  and left the validation PR open without merging.
- [x] 2026-07-25: Added the standalone `?demo=style-party` route plus a local-only
  upload-to-stage path so the H5 can be evaluated without the product API.
- [x] 2026-07-25: Restored the actual runway/ballroom interaction after user review,
  directly reused pinned Pixel Agents scene assets, replaced implicit upload publishing
  with a backstage state, and added runway/spotlight/dance choreography.

## Surprises and discoveries

- The reference makes “pixel character” mean a complete fashion-paper-doll image, not a
  generated CSS block person. Reusing the supplied pixel outputs is both more faithful
  and faster than inventing another character system.
- PR #10's old primary Community tab conflicted with the confirmed two-destination
  product navigation. A secondary wardrobe entry makes the validation honest and
  removable.
- The supplied examples are suitable for a curated theme seed, but not evidence of live
  community participation. Labels and callback boundaries preserve that distinction.
- A complete validation cannot depend on a future RenderArtifact connection. A
  local-only image picker proves the actual UGC-to-share interaction now while keeping
  the production integration boundary intact.

## Decision log

- 2026-07-25 — Movement is not the product by itself, but the runway/dance ritual is
  the participation mechanism that makes UGC feel social instead of like a static card.
- 2026-07-25 — Use only pixel outputs in this PR; real-photo provenance and outfit
  traceability belong to other product slices.
- 2026-07-25 — Keep social actions local in the demo but expose small callback contracts
  so live persistence can be connected without rewriting the screen.
- 2026-07-25 — Do not merge the experiment automatically after verification.
- 2026-07-25 — Keep local uploads browser-only and expose the direct demo as a query
  route, avoiding new persistence, backend, routing, or deployment dependencies.
- 2026-07-25 — Reuse Pixel Agents only at the scene boundary (assets and frame-loop
  pattern); do not import its VS Code, terminal, editor, or pathfinding architecture.


## 2026-07-26 rebuild

The first version drew the room on a canvas and the characters as CSS-positioned
DOM images. They shared no coordinate space, so nobody ever looked like they were
standing in the room, and a second backdrop would have meant a second renderer.

### What changed

- **One world.** Tile maps are data (`world/sceneMap.ts`), with a camera, y-sorted
  drawing, depth scaling, contact shadows and tap-to-move. Adding a location is
  now content, not code — which is how the third scene got added in an afternoon.
- **Animation without sprite sheets.** The supplied art is full-body portraits, so
  `world/characterRig.ts` splits each portrait into head / torso / lower bands and
  animates them procedurally. When the owner supplied a 4-character × 4-pose pack,
  authored poses took over the discrete states (idle / walk / cheer / wave) and the
  rig kept them alive in between.
- **A room that is social without the player.** Guests pair off, walk to each
  other and run their own scripted exchanges; the player can walk over and join, or
  type a line that appears as their own bubble.
- **The share unit is the group shot.** The card names only guests actually inside
  the captured frame, and waits for the crowd to arrive before the shutter fires.

### Asset pipeline

| Script | Input | Output |
| --- | --- | --- |
| `scripts/pixel_look_cutout.py` | illustration cards with frames and backdrops | clean transparent Look sprites |
| `scripts/pixel_pose_cutout.py` | the 4×4 pose pack | `poses/<character>/<pose>.png` |

The ~36 MB source pose pack is not committed; the ~930 KB of derived sprites is,
with source hashes recorded in `apps/h5/public/assets/community/poses/README.md`.

### Verification (2026-07-26)

- 75 unit tests across 12 files; TypeScript and production build clean.
- Real 390×844 Chromium runs: opening state, guest conversation, guest-to-guest
  conversation, player speech, runway, applause, freeze, still card, animated card,
  all three locations, immersive mode enter/exit.
- No horizontal overflow (`scrollWidth === clientWidth === 390`) in either mode.
- Animated card verified mechanically: footer pixels identical across frames,
  scene pixels differing.
- Dev-only helpers (`/device` preview frame, `__styleParty` handle) confirmed
  absent from the production bundle.

### Known gaps

- The coffee house reuses the pink Pixel Agents sofa rather than a purpose-drawn
  one; it is the weakest scene visually.
- Dialogue is authored, not model-driven. That is deliberate for this slice.
- Still no live multiplayer. `sayAsPlayer` is the seam a real second person would
  speak through.
