# ADR 0002: Signed anonymous sessions own uploads and wardrobe assets

- Status: accepted
- Date: 2026-07-25
- Decision owners: StyleCapture-plus engineering loop

## Context

The mobile demo must be immediately operable without a Douyin OAuth tenant, but
the wardrobe and original images are private user assets. A UUID generated in
browser storage and trusted through a request header is not an authentication
boundary: callers can choose another UUID, and an unowned prepared upload can be
claimed by any capture request that knows its object key and hash.

## Decision

The Product API issues an anonymous principal through `POST /v1/session` and
stores it in an `HttpOnly`, `SameSite=Strict`, HMAC-signed cookie. Production
requires a distinct server-side signing secret and `Secure` cookies.

Every prepared upload is bound to that principal in both the signed upload token
and persisted object metadata. Capture submission verifies the stored owner
before checking or revealing other object details. Item, job, source-image,
update, retry, and delete operations resolve the same principal through a shared
FastAPI dependency.

The short-lived upload token is returned in the prepare response and sent only
in the `X-Upload-Token` request header to the fixed `/v1/uploads` endpoint.
Bearer credentials are never placed in URL paths or query strings, where
reverse proxies can copy them into access or error logs.

The browser never supplies a trusted user ID. A future Douyin login adapter may
replace anonymous issuance while preserving the principal and resource
contracts.

Source deletion is separately persisted as an Item tombstone. Deleted bytes are
not served and recognition retries are rejected with
`source_deleted_not_retryable`; the Worker also converts a missing-source race
into a stable terminal `source_unavailable` error.

Deletion removes bytes before committing the tombstone. If the object store
cannot delete, the Item remains visibly source-backed and the same idempotent
delete action can be retried; the system never records a successful privacy
deletion while retaining an inaccessible orphan.

## Consequences

- A copied object key/hash cannot be used by another session to read an original.
- Refreshes retain private identity without exposing the token to JavaScript.
- Clearing cookies creates a new anonymous wardrobe; account linking/migration is
  future OAuth work.
- Revocation and multi-device identity require the future authenticated session
  adapter.
- Provider/model audit metadata remains server-side; public Item responses expose
  only capability/schema/taxonomy fields.
- Upload credentials are short-lived and header-bound. Nginx suppresses raw
  upload access logs, and Uvicorn access logging is disabled behind the reverse
  proxy as defense in depth.
- Authenticated browser traces are disabled because they capture cookies,
  request headers, and uploaded media. Product evidence uses screenshots and the
  separately redacted application trace contract.

## Rejected alternatives

- Client-generated UUID header: spoofable and not private by default.
- Soft delete while retaining retriable bytes: contradicts the user-facing
  promise that deleting the original removes it.
- Waiting for Douyin OAuth before development: would block the locally operable
  product without improving the feature contracts.
