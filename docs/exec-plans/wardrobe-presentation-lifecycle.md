# Wardrobe Presentation Lifecycle

## Purpose / Big Picture

Make every saved Look and Item tell the truth while AI presentation assets are being generated. A user should see the captured source softly blurred while work is pending, the generated real-item collage as soon as all required item images exist, and a pixel cover only after the user explicitly selects it as the wardrobe cover. Upload-, Feed-, and AI-created Looks use the same detail layout. Try-on later reuses the user's persisted profile photos.

## Progress

- [x] 2026-08-09: Configured Doubao capability aliases locally and verified a fresh Feed save reaches `ready`.
- [x] 2026-08-09: Rebuilt the API/worker with migration `20260808_0017`; verified four Item presentation tasks and both Look render tasks succeed.
- [x] 2026-08-09: Added honest blurred pending states and corrected contradictory Item presentation copy.
- [x] 2026-08-09: Added collage/source fallbacks for Look cards without a pixel cover.
- [ ] Persist and expose the user's wardrobe-cover selection.
- [ ] Persist profile reference photos and allow try-on jobs to reuse a selected/default photo.
- [x] 2026-08-09: Passed 31 targeted H5 tests and browser-verified both pending and completed Look states.

## Surprises & Discoveries

- The first real worker run called Doubao successfully but failed while inserting `flat_lay_item`; the running API image had migrations only through `20260726_0016`, so PostgreSQL still rejected the new presentation kind.
- Rebuilding API and worker applied `20260808_0017`. A new Feed capture then completed `capture -> four item presentations -> collage -> pixel cover` without manual database edits.
- The H5 currently auto-displays any successful pixel cover and generates missing pixel covers automatically. This contradicts the requested user-controlled cover choice.
- Profile photos on the “我的” screen currently live only in browser storage, so the backend cannot reuse them for try-on jobs.

- The C: volume has only about 12.5 GB free, below the repository's 20 GB build guardrail. Further Docker rebuilds should wait until the workspace and Docker data are relocated or space is reclaimed.

## Decision Log

- 2026-08-09: Keep processing states driven by Product API job/render states; do not infer completion from image appearance alone.
- 2026-08-09: Reuse existing Look detail, RenderArtifact, ItemPresentation, TanStack Query polling, and profile photo UI. Extend their contracts rather than creating parallel presentation or upload flows.
- 2026-08-09: Treat the source image and deterministic component collage as explicit fallbacks, never as completed AI output.

## Context and Orientation

- Look list/detail UI: `apps/h5/src/features/wardrobe/LookCard.tsx`, `LookDetail.tsx`, `WardrobeScreen.tsx`.
- Item detail/UI state: `apps/h5/src/features/wardrobe/ItemDetail.tsx` and `ItemCard.tsx`.
- Server orchestration: `services/backend/src/stylecapture_backend/features/outfit/infrastructure/presentation.py`, `render`, and `item_presentation`.
- Profile photo UI/storage: `apps/h5/src/features/profile/PhotoManagerSheet.tsx` and `photoStorage.ts`.
- Runtime uses LiteLLM aliases; provider names and keys remain server-only.

## Reuse Audit

| Capability | Candidates inspected | Decision | Reason / source / license |
|---|---|---|---|
| Async UI state | Existing TanStack Query polling and Product API render/item presentation states | Direct reuse | Already versioned and exercised by wardrobe detail; repository code, same license. |
| Real-item fallback | Existing deterministic collage renderer and component-image flatlay | Direct reuse | Meets PRD truthfulness requirement without new model calls; repository code, same license. |
| Pixel cover | Existing RenderArtifact `pixel_cover` pipeline | Adapted reuse | Add selection semantics; do not create a second image pipeline. |
| Try-on subject photos | Existing profile photo picker plus existing try-on signed-upload endpoint | Adapted reuse | Persist metadata/server object keys so both screens share one source of truth. |
| New external libraries | None | Rejected | Existing React/FastAPI/PostgreSQL/Celery contracts cover the slice. |

## Plan of Work

1. Add behavior-first tests for pending/ready Item and Look presentation states.
2. Render a 50% blurred source/component fallback while collage or Item flat-lay work is pending; remove pending labels immediately when the corresponding asset succeeds.
3. Pass collage render state into Look cards and distinguish generated from explicitly selected pixel covers.
4. Add a small Product API mutation for selecting a succeeded pixel cover and refresh the wardrobe list after selection.
5. Add backend-owned profile-photo records and reuse them when starting a try-on, while retaining upload-new as an option.
6. Verify target tests, typecheck/build, backend tests/migrations, and real mobile paths.

## Concrete Steps

- Work from `work/StyleCapture-plus` on `codex/fix-feed-capture-pipeline`.
- Run targeted H5 tests with `pnpm --filter @stylecapture/h5 test -- look-wardrobe` (or the repository-equivalent script).
- Run targeted backend tests through the existing `.venv`/pytest setup.
- Rebuild only API/worker when backend contracts or migrations change; keep worker concurrency at one.
- Exercise Feed save, upload save, AI-created Look, Item detail, pixel selection, and try-on subject reuse at the mobile viewport.

## Validation and Acceptance

- A new Feed capture appears in the wardrobe immediately, then changes to ready without a page reload.
- Pending Look and Item views show a blurred real source plus “单品图生成中，请稍后”; completed assets remove the message.
- Upload-, Feed-, and AI-created Looks share the same detail information architecture.
- A Look card without a selected pixel cover uses a blurred collage/source fallback.
- Selecting a succeeded pixel cover persists and changes the Look card; merely generating it does not.
- Try-on can use the default saved profile photo, another saved photo, or a new upload.
- No secret appears in tracked files, browser bundles, screenshots, or logs.

## Idempotence and Recovery

- Existing render signatures and idempotency keys remain the generation boundary.
- Cover selection is a small repeatable mutation; selecting the already-selected artifact is a no-op.
- Profile photo uploads use existing signed upload validation and can be retried without duplicating active records.
- Failed provider work remains visible and retryable; no placeholder is relabelled as success.

## Outcomes & Retrospective

In progress. Final evidence and remaining limitations will be recorded after the browser and test pass.
