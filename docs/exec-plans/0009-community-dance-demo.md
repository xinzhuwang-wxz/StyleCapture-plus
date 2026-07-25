# Pixel Style Party Demo ExecPlan

> Keep this plan current as behavior, evidence, and product decisions change.

**Issue:** [#9](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/9)
**PR:** [#10](https://github.com/xinzhuwang-wxz/StyleCapture-plus/pull/10)
**Status:** Independent concept validation. This branch may be closed without merging.

## Observable outcome

Replace the free-roaming pixel mini-game with a mobile-first theme Look showcase. A
user enters from the digital wardrobe, browses complete fashion-pixel Looks, collects
an inspiration, publishes their own pixel Look to the current theme, leaves a
style-specific reaction, and downloads a share card.

The experiment tests one product hypothesis:

`theme prompt → publish pixel Look → receive/browse style signals → collect → share → new participation`

It does not add a live community backend, primary navigation destination, real-time
presence, or a general game engine.

## Product and interaction decisions

- **Scene:** `花房晚宴`, a soft pixel-fashion greenhouse stage rather than a map.
- **UGC:** `带我的 Look 登场` is the central action and calls a replaceable
  `onPublishLook` boundary with the visible pixel artifact.
- **Social:** responses describe why a Look works (`配色好会`, `层次感`,
  `想抄作业`) instead of fabricated likes or follower counts.
- **Retention:** curated Looks can be collected locally as styling inspiration through
  a replaceable `onSaveInspiration` boundary.
- **Distribution:** the current visible pixel image becomes a downloadable share card;
  loading, duplicate taps, Canvas failure, and retry are explicit.
- **Independence:** the wardrobe contains a secondary experiment card. The confirmed
  Feed / Wardrobe primary navigation is unchanged, and the feature can be removed as
  one overlay module.
- **Truthfulness:** supplied examples are labelled `精选示例 · 非真人`; local state is
  labelled `非实时社区`.

## Reuse audit

| Capability | Candidate | Decision | Reason | Source / commit / license |
| --- | --- | --- | --- | --- |
| H5 shell, interaction, motion | Existing React/Vite/Motion application | Direct reuse | Preserves one deployable H5 and avoids a second runtime | This repository at base `7747783`; React, Vite and Motion are MIT |
| Pixel Look presentation | User-provided `素材库.zip` (`像素图1-3.png`) | Direct reuse of the three pixel-only examples | They match the product's complete fashion-pixel silhouette and require no new avatar engine | User-provided project asset, 2026-07-25; hashes recorded in `apps/h5/public/assets/community/README.md` |
| Free movement / multiplayer / game scene | Previous DOM map and earlier game-engine candidates | Rejected and removed | Movement did not support the UGC/share hypothesis; a game or multiplayer dependency would broaden an experiment that needs no live room | No external package copied or added |
| Share export | Browser Canvas 2D | Direct reuse | Local, dependency-free export of the same public pixel image visible on stage | Browser platform API |

## Acceptance checklist

- [x] Secondary wardrobe entry opens an isolated full-screen experience.
- [x] The first viewport explains the theme and value proposition.
- [x] Three complete pixel-fashion examples can be browsed and are labelled as examples.
- [x] The supplied `avatarSource` is the same image shown on stage and exported.
- [x] A user can publish their Look, collect a curated Look, and leave a style reaction.
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

## Surprises and discoveries

- The reference makes “pixel character” mean a complete fashion-paper-doll image, not a
  generated CSS block person. Reusing the supplied pixel outputs is both more faithful
  and faster than inventing another character system.
- PR #10's old primary Community tab conflicted with the confirmed two-destination
  product navigation. A secondary wardrobe entry makes the validation honest and
  removable.
- The supplied examples are suitable for a curated theme seed, but not evidence of live
  community participation. Labels and callback boundaries preserve that distinction.

## Decision log

- 2026-07-25 — Validate a theme-based UGC/social/share loop, not a movement mechanic.
- 2026-07-25 — Use only pixel outputs in this PR; real-photo provenance and outfit
  traceability belong to other product slices.
- 2026-07-25 — Keep social actions local in the demo but expose small callback contracts
  so live persistence can be connected without rewriting the screen.
- 2026-07-25 — Do not merge the experiment automatically after verification.
