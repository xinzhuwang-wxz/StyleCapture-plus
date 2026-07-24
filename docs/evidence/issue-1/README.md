# Issue #1 evidence — upload or photograph a real garment

## Outcome

A real mobile browser selected a real JPEG, chose its ownership, uploaded it through the signed upload API, created a durable Capture, and observed PostgreSQL/Redis/Celery processing. With the LiteLLM provider intentionally unavailable, the worker retried three times, persisted `vision_unavailable`, exposed a recoverable error Item, and never fabricated tags.

The same browser then retried the job, edited classification/description/ownership, and deleted the source using an in-product two-step confirmation. The API returned the deleted source as 404 after reload while the text asset remained in the wardrobe. A follow-up E2E deleted the source while an automatic Worker retry was pending and proved that the durable tombstone and locked user truth survive the stale Worker write.

## Screenshot evidence

All screenshots use a 390×844 viewport and the real local API. No network route was intercepted.

- [`01-empty-wardrobe-mobile.png`](../../../artifacts/issue-1/01-empty-wardrobe-mobile.png) — reusable StyleCapture shell and empty state.
- [`02-upload-confirmation-mobile.png`](../../../artifacts/issue-1/02-upload-confirmation-mobile.png) — real image preview and required ownership selection.
- [`03-provider-unavailable-mobile.png`](../../../artifacts/issue-1/03-provider-unavailable-mobile.png) — honest failure state with retained image and retry.
- [`04-item-detail-mobile.png`](../../../artifacts/issue-1/04-item-detail-mobile.png) — source image and editable Item detail.
- [`05-item-detail-actions-mobile.png`](../../../artifacts/issue-1/05-item-detail-actions-mobile.png) — corrected fields and reachable bottom actions after the scroll fix.
- [`06-delete-confirmation-mobile.png`](../../../artifacts/issue-1/06-delete-confirmation-mobile.png) — accessible in-page destructive confirmation.
- [`07-source-deleted-mobile.png`](../../../artifacts/issue-1/07-source-deleted-mobile.png) — deleted source replaced immediately by a privacy-safe placeholder.
- [`08-source-deleted-reload-mobile.png`](../../../artifacts/issue-1/08-source-deleted-reload-mobile.png) — the same privacy-safe state after a full reload; the retry action remains unavailable.

## Fresh verification

```text
Python: 66 passed
Python static checks: Ruff, format, mypy, architecture boundaries passed
H5: 4 Vitest tests passed
H5: TypeScript check and Vite production build passed
Contract: OpenAPI regeneration stable; Python and cURL examples returned 201/201/201/202
Container: full Compose healthy; every service uses a read-only root filesystem,
  no-new-privileges, and dropped/minimum capabilities; every host port is loopback-only
Mobile E2E: 1 passed in 7.7s with real API, PostgreSQL, Redis, Celery, reload, and a redacted screenshot
Visual verdict: 92 / pass
Dependency audit: no known vulnerabilities in Python or pnpm environments
```

## Real path observed

```text
mobile JPEG
  -> signed PUT
  -> HTTP 202 Capture + ProcessingJob
  -> Redis capture queue
  -> Celery concurrency=1
  -> LiteLLM capability alias
  -> 3 bounded retries
  -> explicit vision_unavailable
  -> error Item + retry
  -> user-locked corrections
  -> source deletion during pending retry
  -> monotonic tombstone + terminal source_unavailable
  -> 404 after reload + retry hidden
```

## Privacy and large-file probe

The real 1,700,105-byte `/Users/bamboo/Downloads/IMG_2310.HEIC` completed the public H5/Nginx upload contract:

```text
session 201 (HttpOnly, SameSite=Strict)
prepare 201
upload 201
capture 202
cross-session claim 404 upload_not_found
anonymous wardrobe read 401 session_invalid
deleted item source_available=false
deleted image 404 item_source_not_found
deleted retry 409 source_deleted_not_retryable
```

The short-lived upload credential is carried in `X-Upload-Token`, never in the
URL path or query string. A live prepare/upload probe confirmed that Nginx and
Uvicorn logs contain only the fixed endpoint and no bearer value; Nginx also
suppresses raw upload access logs.

Playwright tracing is disabled for authenticated product tests because a raw
browser trace records cookies, request headers, and uploaded media. The
credential-bearing trace discovered during security review was deleted rather
than retained as evidence. Mobile proof uses explicit screenshots plus fresh
test output; future product Workflow traces must use the application-level
redacted trace contract.

All Compose host ports are bound to `127.0.0.1`; service-to-service traffic stays
on the private Docker network. Pillow 12.3.0 and pillow-heif 1.5.0 are pinned,
and magic-byte validation rejects a mismatched format before invoking the image
parser. Upload parsing runs off the API event loop behind a two-slot application
semaphore; Nginx independently applies a two-connection limit and bounded request
rate. Every `/v1/` response is marked `Cache-Control: private, no-store` and
varies by cookie.

All base and state-service container images are pinned to the digests used by
the verified build.

Concurrent replay of the same signed upload is idempotent: object and metadata
writes use unique atomic temporary files, and both callers receive the same
stored-object result.

## Environment-gated evidence

No `ARK_API_KEY` was available during this pass. Therefore a successful Doubao response and the FashionSigLIP `ai-light` smoke are not claimed. Their adapters, schemas, resource-limited container profile, and contract tests are present; the product failure path remains honest and usable without them.

The browser/API/worker stack used one local PostgreSQL container (~29MB), one Redis container (~10MB), one API process (~79MB), one Celery worker with concurrency 1 (~311MB), one LiteLLM gateway (~287MB), and one Nginx H5 container (~9MB). No local vision model was loaded.
