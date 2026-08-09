# ADR 0007: Wardrobe asset deletion and shared Items

## Status

Accepted

## Context

A Look is a relationship over canonical wardrobe Items. The same Item may be reused by several Looks, while generated covers and collages are derived from those relationships. Blind cascading would either delete shared wardrobe truth or leave stale presentations visible.

## Decision

- Look deletion is scoped by the user: delete only the Look, or delete the Look plus its now-unreferenced Items.
- Items referenced by another Look are never deleted as part of Look deletion.
- Direct Item deletion detaches every Look component that references it, marks those Looks partial, and invalidates their generated render records.
- Deletion is atomic in PostgreSQL and is rejected while the target is processing.
- The API reports deleted and preserved Item IDs so the client can explain the outcome.

## Consequences

This preserves shared Items and prevents stale database-visible covers, at the cost of some Looks becoming partial after direct Item deletion. Derived blobs may remain until normal object-retention cleanup; immediate privacy-grade blob erasure requires a transactional outbox rather than synchronous best-effort deletes.
