# ADR 0003: Keep user truth monotonic across asynchronous Worker saves

- Status: Accepted
- Date: 2026-07-25
- Scope: Item persistence shared by capture processing and product editing

## Context

An Item is updated by two actors with different authority:

- the user controls ownership, locked corrections, and whether the original source remains available;
- the asynchronous Worker controls processing status, model-derived fields, model metadata, and embeddings.

The first implementation persisted both actors through one whole-record `merge`. A Worker can hold an Item snapshot while the user deletes the source or corrects a field. Saving that stale snapshot after the user action could restore `source_available=true`, revert ownership, or remove a locked correction. Domain-level locked fields are insufficient because they only protect values visible in the Worker snapshot.

## Decision

Use two repository write paths under a PostgreSQL row lock:

1. `save` is the Worker path. It may advance processing/model state, but it:
   - preserves the current database ownership;
   - preserves every currently locked field;
   - merges rather than replaces model attributes and metadata;
   - never changes `source_available` from `false` back to `true`;
   - does not erase an existing embedding with an empty Worker result.
2. `save_user_state` is the product path. It may:
   - update ownership;
   - add or replace fields only when they are user-provenance and locked;
   - change source availability only from `true` to `false`.

Both paths reload and return the stored Item after commit so subsequent application steps use the authoritative merged state rather than a stale input object.

## Consequences

- Source deletion is a monotonic privacy action.
- A model retry cannot overwrite a user correction or ownership choice.
- Concurrent user and Worker writes remain deterministic without holding a database lock during provider calls.
- Future features must classify Item fields by writer authority before adding them to either path.
- If collaborative multi-user editing is introduced, user-to-user conflicts still need an explicit revision/version contract; this ADR only resolves user-versus-Worker authority.

## Rejected alternatives

- **Whole-record optimistic locking only.** It detects a conflict but forces retry orchestration across Celery and HTTP without defining which actor is authoritative.
- **Hold a row lock during model inference.** This would serialize slow external calls and make the product vulnerable to provider latency.
- **Soft-delete while retaining source bytes.** It conflicts with the user-visible promise that deleting the original makes it inaccessible.
- **Infer user writes from value differences.** This is ambiguous and would couple persistence to current UI behavior.

## Verification

- Integration regression: a stale Worker snapshot saved after user ownership correction, locked classification, and source deletion preserves all three user decisions while advancing Worker status.
- Mobile E2E: delete during an automatic retry, reload, observe the privacy placeholder, and verify no retry action is offered.
- API probe: deleted image returns `item_source_not_found`; deleted retry returns `source_deleted_not_retryable`.
