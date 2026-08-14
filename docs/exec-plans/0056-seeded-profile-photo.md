# Seeded profile reference photo

## Goal

Issue #96 makes the authorized roadshow portrait immediately available in every
fresh H5 session. A user can see it in `我的形象照` and choose the same photo from
the Look-detail try-on picker without uploading a file during the demo.

The observable outcome is client-side and deployment-wide. This slice does not
add a second photo store, persist private user photos on the server, or change the
try-on provider. Existing local albums remain authoritative when they exist.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Shared profile-photo album | `photoStorage.ts`, `ProfileScreen`, `PhotoManagerSheet`, `TryOnPhotoSheet` | Adapted reuse | Both the profile and try-on journey already share one validated album. A seeded fallback reaches both without a parallel state path. | Repository `main@3c0fc67`, project license |
| Portrait preparation | Existing `downscaleToDataUrl` 720 px non-cropping JPEG policy | Direct reuse of policy | The bundled image should have the same size and framing as a locally saved reference photo. | Repository `main@3c0fc67`, project license |
| Authorized portrait | User-supplied `微信图片_20260814125646_2671_1976.jpg` | Adapted reuse | The product owner explicitly supplied this image for the shared roadshow preset. It is resized without cropping and stripped of source metadata before commit. | Source SHA-256 `c478b324cb974737c8eb21b5d1f5512d90e292afc226201db7cab99737af1f5a`; 540x720 derivative SHA-256 `62fd127e081db66994281b1163d416d9c7df17a38550cbb8c5e568c0ed8603f4`; product-owner authorization in Issue #96 |
| Server-side profile persistence | Existing signed upload/object-store contracts | Rejected | The roadshow requirement is a common bundled preset, not cross-device persistence of each user's sensitive private photos. A backend migration would add latency and privacy scope without improving this outcome. | Repository `main@3c0fc67`, project license |

## Decisions

1. Bundle a 720 px JPEG derivative in the H5 source and inline it at build time,
   so the existing album's `data:image/` invariant and synchronous file conversion
   remain unchanged.
2. Use the preset only as the album fallback when no valid localStorage value
   exists. A previously saved album, including an intentionally empty album,
   remains untouched.
3. Make the preset the active try-on photo in that fresh fallback album.
4. Keep the preset subject to the existing album management behavior. If a user
   deletes it, the persisted empty album wins on future loads instead of silently
   restoring a photo they removed.
5. Keep descriptive Item/Look naming out of this branch and PR.

## Verification plan

- Add a failing storage behavior test for a fresh session, then implement the
  minimum seeded fallback.
- Keep round-trip, validation, capacity, activation and deletion tests passing.
- Run H5 focused tests, typecheck and production build.
- Operate a 390x844 browser journey through the profile and photo manager;
  capture initial, interaction, deletion, and reload states. Re-run the shared
  Look-detail photo-picker component tests against the same album contract.
- Check the bundled derivative visually against the supplied original and record
  a Visual Verdict of at least 90 before PR handoff.

## Verification results

- Behavior-first red: `photo-album.test.ts` failed with zero fresh-session photos.
- Behavior green: the same focused module passed all 15 tests after the seeded
  fallback implementation.
- Focused profile tests passed 29/29 across photo storage, photo management, and
  the shared try-on picker.
- The App profile integration test passed and sees the same active seeded photo on
  both the profile strip and management subpage.
- H5 typecheck passed.
- H5 production build passed with 548 modules transformed. The inlined reference
  keeps the deployed behavior independent of machine-local paths.
- The broader `app.test.tsx` run had 35 passing tests and one existing unrelated
  visibility assertion failure in the Look item action sheet; that failure also
  reproduces in isolation and does not touch profile code.
- Playwright CLI operated the real H5 at 390x844 through fresh profile, management,
  selection, deletion, and post-reload persistence. Screenshots and review are in
  `docs/evidence/issue-96/`.
- Visual Verdict: 96/100; no P0/P1 visual defect.

## Review results

- Spec compliance: clean. Every Issue #96 criterion is represented by a storage,
  App, shared-picker, build, or browser check; naming work remains excluded.
- Code quality and security: clean. The change reuses the validated data-URL album,
  adds no URL allowlist exception, network fetch, server secret, raw source path, or
  provider payload. The committed JPEG exposes only generic image properties.
- Architecture: clean. The preset is a fallback of the existing profile feature;
  no second state store, backend DTO, persistence table, or try-on implementation
  was introduced.
- User experience: clean. The full reference remains uncropped in management,
  active and selection states remain clear, and deletion remains durable.

## Progress

- [x] Confirm latest upstream `main@3c0fc67` and create an isolated worktree.
- [x] Inspect the shared local album and try-on path.
- [x] Create Issue #96 with observable acceptance criteria.
- [x] Add the behavior-first failing test.
- [x] Prepare and bundle the authorized portrait.
- [x] Implement the fresh-session preset fallback.
- [x] Run focused and production verification.
- [x] Complete mobile visual review and record evidence.

## Surprises & discoveries

- The current profile header portrait is decorative and separate from the actual
  try-on album. Replacing it alone would not make the supplied photo selectable.
- The album deliberately rejects ordinary URLs. Inlining the curated derivative
  preserves that privacy boundary and avoids changing the synchronous try-on file
  conversion contract.
- Two older Vite processes already occupied 5173/5174. The first browser probe hit
  an old build, so final evidence used strict isolated port 5186 and confirmed the
  served `photoStorage.ts` contained the new fallback before review.

## Decision log

- 2026-08-14: Use the existing client album fallback instead of backend profile
  persistence because the requested roadshow behavior is a common bundled preset
  and must ship independently of private per-user storage.
