# Community Pixel Runway Design

## Goal

Turn the Community tab into a complete, interactive mobile H5 demo where every visible
character is a pixel avatar and the user can bring their own avatar onto a fashion runway.

## Chosen Direction

The existing ballroom becomes **StyleCapture Runway Night**. The central runway is the
primary interaction: residents take a looped turn, while the user can press `轮到我上台`
to enter a short runway state. It keeps the dance-floor energy as a backstage detail but
makes outfits and being seen the reason to interact.

## Experience

1. The Community tab opens on a dense pixel night scene: a runway, three named pixel
   residents, a small pixel audience, spotlights, a live lookboard, and a backstage zone.
2. Every person is a pixel avatar. Residents use distinct pixel silhouettes and their
   public tags remain available from their avatar button. The user avatar uses the same
   replaceable public avatar-source seam from the prior demo.
3. The header names the currently featured resident. Pressing `轮到我上台` moves the user
   avatar to the runway, starts a restrained runway loop, changes the scene announcement,
   and increments an applause count.
4. The four existing reactions remain, but now visibly appear as a crowd/spotlight event
   around the runway. Selecting a reaction while the user is on stage updates the show
   copy and the exported share card.
5. The live lookboard shows only a character name, public tags, and an explicitly public
   demo label. It never shows original references, private Items, or a fake live-user
   claim.
6. The share card is a real browser PNG download containing the current pixel avatar,
   runway state, selected reaction, and applause count. Canvas export failure remains
   retryable.

## Interaction and Accessibility

- Tapping the runway or the `轮到我上台` button puts the user on stage; tapping backstage
  returns them to the scene.
- Movement fallback controls and arrow-key navigation remain available.
- Resident buttons remain keyboard accessible; their modal is explicitly non-human,
  modal, Escape-closeable, focus-trapped, and focus-restoring.
- The stage remains a labelled `region`, not an ARIA `application`.
- Reduced-motion users see state changes without looping animation.

## Technical Boundaries

- Keep React/Vite H5, the current Community feature-local state model, and local Canvas
  export. Do not add a game engine, iframe, multiplayer service, provider call, or new
  dependency.
- All resident data is deterministic, labelled scene data. The user avatar remains an
  explicit `CommunityAvatarSource` with a labelled demo fallback until a public Look
  RenderArtifact is available.
- CSS/DOM renders the runway; Canvas is solely a local share-card renderer.

## Acceptance Evidence

- A 390×844 browser journey captures initial runway, a resident public-style sheet, the
  user on stage with a reaction, successful share download, export failure, and recovery.
- Unit/component tests cover runway entry/exit, applause/reaction state, existing bounds,
  resident semantics, modal keyboard behavior, and share rendering.
- Typecheck, full H5 test suite, production build, mobile Playwright run, and a visual
  verdict of at least 90 pass before the PR update.
