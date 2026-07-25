# Pixel Dance Community Demo ExecPlan

> **For agentic workers:** keep this plan current as behavior, evidence, and decisions
> change. Work one observable vertical slice at a time.

**Issue:** [#9](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/9)
**Goal:** Add a deployable, mobile-first Community tab where a user can move a pixel
avatar around a dance-floor scene, trigger a dance and expressive reactions, inspect
clearly labelled scene residents, and export a privacy-safe share card.

**Architecture:** Keep the experience inside the existing React/Vite H5 shell. A
feature-local scene reducer owns only local demo position, animation, resident focus,
and share-card state. CSS/DOM renders the accessible interactive scene; a local Canvas
exports its share card. React owns the accessible controls, drawer, error/retry state,
and navigation. The avatar source is an explicit replaceable `CommunityAvatarSource`:
this baseline uses the approved demo pixel identity until Issue #3/#5 supplies a public
Look RenderArtifact. No user reference image, private Item source, or provider result is
sent to the browser. Future live presence can replace the local action dispatch with the
same public `CommunityPresence` contract.

## Constraints

- No iframe, second standalone app, runtime stub presented as a real person, or Node
  game server in this Issue.
- Scene residents are visibly labelled `场景居民`; only public style tags are shown.
- The scene must be operable through touch/click and keyboard controls, with reduced
  motion respected.
- The share image must be generated locally from public scene state and either download
  successfully or show an actionable retry state.
- Existing Feed and wardrobe interaction must keep working.

## Reuse Audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Pixel scene rendering and motion | Pixel Agents; CSS/DOM; Canvas API; Phaser | Adapt CSS/DOM motion and use Canvas only for local share export | Pixel Agents proves the visual direction but is an editor/agent product; the existing DOM shell keeps this demo accessible without a second runtime/dependency | Pixel Agents, current main, MIT; browser Canvas API |
| Multiplayer architecture | Agent Office; Colyseus | Reject for current slice | It supplies real-time Phaser/Colyseus rooms, but mobile support is not established and a Node server would broaden the product topology before demand is proven | Agent Office, current main, MIT |
| Maps, movement and mobile controls | RPGJS v5 | Reject for current slice | Strong future map-room option, but its CanvasEngine/Vue runtime is disproportionate for one small scene | RPGJS v5, current main, MIT |
| Existing application shell | `apps/h5` App, Motion, React, Vite | Direct reuse | Preserves one session, theme, navigation, and deployment path | This repo `52e8aa5`; React 18/Motion/Vite MIT |

## Plan of Work

1. Add a pure scene model for bounds, dance-floor detection, deterministic residents,
   movement target, and emoji selection. Prove it through focused red-green tests.
2. Add an accessible `CommunityScreen` that renders a CSS/DOM pixel ballroom, routes
   taps and keyboard motion through the model, exposes an always-visible movement
   fallback, and uses Canvas only for local PNG share-card export.
3. Add a resident detail sheet and a local share-card generator with loading, success,
   failure, and retry states.
4. Integrate the Community destination into the existing three-item mobile navigation
   without changing Feed/wardrobe contracts.
5. Run targeted H5 tests, typecheck, production build, and a real mobile Playwright
   journey with screenshots for initial, interaction, success, failure, and recovery.

## Acceptance Checklist

- [x] Community tab opens inside the existing H5.
- [x] Tap/click ground and keyboard controls move the avatar within scene bounds.
- [x] Entering the dance floor visibly enables a dance loop.
- [x] Four reactions are usable and visible.
- [x] Resident identity is explicitly non-human and exposes only public tags.
- [x] Share card has working download and recoverable failure state.
- [x] Mobile screenshots and fresh automated evidence are captured, including the runway
  state after `轮到我上台`.

## Progress

- [x] 2026-07-25: Issue #9 created and branch `codex/issue-9-community-dance-demo`
  created in an isolated worktree.
- [x] 2026-07-25: Reviewed current H5 shell, navigation, pixel theme, and local resource
  guardrails.
- [x] 2026-07-25: Established H5 baseline: 7 files / 28 tests passed.
- [x] 2026-07-25: Added behavior-first scene model and CommunityScreen tests, including a
  verified red-green cycle for bounds/dance state and keyboard movement.
- [x] 2026-07-25: Implemented the in-H5 Community scene and three-item navigation.
- [x] 2026-07-25: Captured 390×844 Playwright evidence for initial, dancing, resident
  inspection, share success, and export-failure recovery. Visual verdict: 94/100 pass.
- [x] 2026-07-25: Independent reviews required an explicit avatar-source seam, truthful
  non-live presence copy, a scene-faithful share card, and modal keyboard/reader support;
  all were incorporated before final verification.
- [x] 2026-07-25: Fresh full H5 suite (9 files / 35 tests), typecheck, production build,
  and two mobile Playwright journeys passed after the final accessibility update.
- [x] 2026-07-25: Extended the mobile Playwright journey through `轮到我上台`, asserted
  the `正在走秀` live-region status, and captured `08-community-runway.png` at 390×844.
- [x] 2026-07-25: Replaced the shared abstract block-person presentation with complete
  fashion-pixel profiles (hair, skin, outfit, trim, shoes, and accessory) for the user,
  residents, and audience. The fallback share card now draws the same profile; a future
  public Look RenderArtifact still takes precedence. Fresh verification: 9 Vitest files /
  37 tests, typecheck, production build, and 2 mobile Playwright journeys passed.
- [ ] Update Issue, commit, push, and open the experience PR.

## Surprises & Discoveries

- 2026-07-25: The current branch is a clean pre-Issue-3 baseline while the primary
  checkout has unrelated uncommitted Look-decomposition work. The community slice is
  isolated in a sibling worktree to preserve that work.
- 2026-07-25: A first Playwright mobile pass found that the dance-floor decoration
  intercepted pointer events. The scene now ignores only actual buttons, so tapping any
  non-interactive map layer moves the avatar. The red run and the repaired green run are
  recorded in the terminal evidence.
- 2026-07-25: Browser Canvas export is available in Chromium but not in jsdom. The test
  environment supplies a minimal Canvas 2D context; browser E2E verifies the actual PNG
  download and separately injects a browser-level export failure to prove recovery.
- 2026-07-25: The clean base predates the public Look RenderArtifact provider. The
  `CommunityAvatarSource` seam is deliberately visible as `Demo 像素形象` rather than
  implying a per-Look cover is already present. It accepts the future public artifact URL
  without exposing an original reference image.
- 2026-07-25: Runway evidence uses the same public avatar-source boundary. It verifies the
  user-facing handoff point for a future public Look RenderArtifact without changing the
  browser contract or leaking private Item/reference media.
- 2026-07-25: The screenshot reference clarified that "pixel avatar" means a complete
  fashion-paper-doll silhouette, not a colored capsule. The scene now carries a small,
  replaceable `PixelDollProfile` per visible character, avoiding a speculative game-avatar
  system while making the future RenderArtifact handoff explicit.

## Decision Log

- 2026-07-25 — Ship local, explicitly simulated scene residents before adding shared
  presence. This gives a truthful, deployable mobile interaction demo without claiming
  a live social graph or introducing an unneeded real-time service.
- 2026-07-25 — Keep the default pixel identity as a labelled, replaceable fallback in this
  demo; real Look artwork remains a derived RenderArtifact integration, not a Look fact.
- 2026-07-25 — Keep default share cards profile-rendered while the source is the labelled
  fallback; draw the supplied image only when it is a public RenderArtifact. This preserves
  a coherent demo visual without weakening the public-asset boundary.
