# Wardrobe asset deletion

## Goal

Allow users to delete a wardrobe item or a saved Look from its detail view, with an explicit scope choice for Look deletion and a final destructive confirmation.

## Progress

- [x] Add authenticated DELETE endpoints for Items and Looks.
- [x] Preserve Items that are still referenced by another Look.
- [x] Detach a directly deleted Item from affected Looks and invalidate stale covers/renders.
- [x] Refuse deletion while the target is still processing so an asynchronous worker cannot recreate it.
- [x] Add detail-page trash actions and staged confirmation dialogs.
- [x] Refresh client caches after deletion.
- [x] Regenerate the OpenAPI client contract and use typed client calls.
- [x] Add repository, HTTP, and UI tests.
- [x] Complete the mobile browser smoke test without deleting real local data.

## Reuse audit

The implementation reuses the existing wardrobe and Look applications, repositories, signed-session principal, React Query cache, detail top bars, and action-button styles. It does not introduce a second storage model or a parallel API client.

## Decisions

1. “Delete Look only” removes the Look and its Look-owned rows while keeping all Items.
2. “Delete Look and Items” deletes only Items that are no longer referenced by another Look; shared Items are reported and preserved.
3. Direct Item deletion removes Look-component references, marks affected Looks partial, and invalidates their generated renders.
4. Processing Items/Looks return HTTP 409. This prevents a queued worker from resurrecting a physically deleted row.
5. Object-store blobs follow the deployment's retention cleanup; the synchronous operation removes database-visible assets atomically.

## Verification

- Backend focused suite: 29 passed.
- H5 TypeScript typecheck: passed.
- H5 focused suite: 64 passed, including all deletion scenarios.
- Mobile Playwright smoke test against `http://localhost:5173`: 1 passed; it exercised scope selection, final confirmation, back, and cancel without submitting a deletion.

## Follow-up

If immediate physical blob erasure becomes a privacy requirement, add an object-deletion outbox so database commit and object-store cleanup remain retryable and observable.
