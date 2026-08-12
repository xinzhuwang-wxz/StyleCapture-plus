# Curated demo storage containment and cloud acceptance

## Outcome

Keep the public cold-start wardrobe unchanged while preventing each anonymous session
from consuming another full copy of the immutable curated image corpus. Preserve per-user
object keys, authorization, metadata, deletion behavior, and all user-upload storage
semantics. Re-run the real public mobile journeys after deployment.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Immutable curated bytes | Existing `LocalObjectStore` atomic temp-and-replace writes; POSIX hard links; a second blob service | Adapt existing object store with POSIX hard links | Keeps every Product API object key and metadata record while sharing only byte-identical checked-in seed assets; no new service or dependency | This repository at `88b3c54`; Python/POSIX standard library |
| Same-session seed concurrency | Existing `CuratedDemoWardrobeBootstrapper`; database idempotency; a new distributed lock | Adapt the existing bootstrapper with an async per-user single-flight lock | Production runs one API process; the database remains authoritative and the filesystem blob write also has an OS lock | This repository at `88b3c54`; Python standard library |
| Public acceptance | Existing Playwright mobile journeys | Direct reuse and update stale selectors/copy | Exercises the real public API, provider, persistence, refresh, recovery, and deletion paths without a parallel smoke harness | This repository at `88b3c54`; Playwright Apache-2.0 |

## Progress

- [x] Diagnose the production wardrobe failure as exhausted root storage, not lost user data.
- [x] Recover 36 GiB by hard-linking only content-identical curated seed files and pruning unused build cache; preserve volumes, secrets, uploads, and user assets.
- [x] Add regression tests proving cross-user curated objects share immutable bytes and ordinary assets remain independent.
- [x] Serialize concurrent bootstrap calls for the same user in the current API process.
- [x] Refresh stale mobile acceptance selectors and assertions to the current product copy and graceful image-generation states.
- [ ] Publish, review, merge, and deploy the exact `origin/main` commit.
- [ ] Re-run the public health, navigation, upload, AI, saved-Look, try-on, pixel-trial, persistence, recovery, and cleanup matrix.

## Surprises & discoveries

- The 50 GiB production root filesystem reached 100% because every anonymous demo
  session stored private-path copies of the same curated source and derived bytes. The
  existing corpus occupied roughly 34 GiB logically but only about 460 MiB after safely
  hard-linking byte-identical curated files.
- The upload journey itself completed model understanding and produced a normalized
  display asset. Its old assertion failed because the UI now says `已整理` instead of
  `可搭配`, and pixel/flat-lay enhancement may honestly remain on the source-image
  fallback while a retry is available.

## Decision log

- Share bytes only for `originals/curated-seed/` and `derived/curated-seed/`. Never
  content-deduplicate ordinary user uploads or generated personal artifacts because
  shared cache retention would weaken user deletion semantics.
- Keep per-user object keys and sidecar metadata. Deleting one user's seed object unlinks
  only that path; other sessions and the content-addressed seed blob remain readable.
- Treat a ready normalized item plus an honest source-image fallback as a usable upload
  result. Stochastic pixel and flat-lay enhancements remain separately retryable and
  must not make the core item disappear.
