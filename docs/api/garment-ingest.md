# Garment ingest API

Issue #1 exposes one provider-neutral API path for uploading a real garment image and following its durable processing state. The browser and external clients use the same contract. Concrete model IDs and provider credentials never appear in these requests.

## Contract flow

1. Establish a private, signed browser session with `POST /v1/session`.
2. Prepare a hash- and session-bound upload with `POST /v1/uploads/prepare`.
3. Upload the exact bytes to `upload_url` with the short-lived
   `X-Upload-Token` returned by the prepare call.
4. Confirm an immutable Capture with `POST /v1/captures`.
5. Poll `GET /v1/jobs/{job_id}` or subscribe to `/events`.
6. Read the resulting assets with `GET /v1/items`.
7. Retry failures, apply user corrections, or delete the source through the Item API.

The API issues an `HttpOnly`, `SameSite=Strict`, HMAC-signed session cookie. The
browser never chooses or sends a trusted user ID. Prepared uploads are bound to
that server-issued principal, so another session cannot claim the object even if
it learns the object key and hash. A future Douyin login adapter can replace
anonymous session issuance without changing the Item or Capture contracts.

## cURL example

The example requires a running stack, `jq`, and a JPEG named `garment.jpg`.

```bash
export STYLECAPTURE_FILE="garment.jpg"
export STYLECAPTURE_SHA256="$(shasum -a 256 "$STYLECAPTURE_FILE" | awk '{print $1}')"
export STYLECAPTURE_BYTES="$(stat -f %z "$STYLECAPTURE_FILE")"

curl --fail-with-body \
  --request POST http://localhost:5173/v1/session \
  --cookie-jar /tmp/stylecapture-cookie.txt \
  --cookie /tmp/stylecapture-cookie.txt

curl --fail-with-body \
  --request POST http://localhost:5173/v1/uploads/prepare \
  --cookie /tmp/stylecapture-cookie.txt \
  --header 'Content-Type: application/json' \
  --data "{
    \"file_name\": \"garment.jpg\",
    \"content_type\": \"image/jpeg\",
    \"byte_size\": ${STYLECAPTURE_BYTES},
    \"sha256\": \"${STYLECAPTURE_SHA256}\"
  }" > /tmp/stylecapture-upload.json

export STYLECAPTURE_UPLOAD_URL="$(jq -r .upload_url /tmp/stylecapture-upload.json)"
export STYLECAPTURE_UPLOAD_TOKEN="$(jq -r .upload_token /tmp/stylecapture-upload.json)"
export STYLECAPTURE_OBJECT_KEY="$(jq -r .object_key /tmp/stylecapture-upload.json)"

curl --fail-with-body \
  --request PUT "http://localhost:5173${STYLECAPTURE_UPLOAD_URL}" \
  --cookie /tmp/stylecapture-cookie.txt \
  --header 'Content-Type: image/jpeg' \
  --header "X-Upload-Token: ${STYLECAPTURE_UPLOAD_TOKEN}" \
  --data-binary "@${STYLECAPTURE_FILE}"

curl --fail-with-body \
  --request POST http://localhost:5173/v1/captures \
  --cookie /tmp/stylecapture-cookie.txt \
  --header 'Content-Type: application/json' \
  --header "Idempotency-Key: $(uuidgen)" \
  --data "{
    \"object_key\": \"${STYLECAPTURE_OBJECT_KEY}\",
    \"sha256\": \"${STYLECAPTURE_SHA256}\",
    \"source_kind\": \"upload\",
    \"ownership\": \"owned\"
  }" | tee /tmp/stylecapture-capture.json
```

The final call returns HTTP 202 with `capture_id`, `job_id`, `status_url`, and `events_url`.

## Python example

This example performs the same contract with `httpx`; it does not call a provider directly.

```python
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx

base_url = "http://localhost:5173"
garment = Path("garment.jpg")
payload = garment.read_bytes()
digest = sha256(payload).hexdigest()

with httpx.Client(base_url=base_url, timeout=30) as client:
    session = client.post("/v1/session")
    session.raise_for_status()

    prepared = client.post(
        "/v1/uploads/prepare",
        json={
            "file_name": garment.name,
            "content_type": "image/jpeg",
            "byte_size": len(payload),
            "sha256": digest,
        },
    )
    prepared.raise_for_status()
    upload = prepared.json()

    stored = client.put(
        upload["upload_url"],
        content=payload,
        headers={
            "Content-Type": "image/jpeg",
            "X-Upload-Token": upload["upload_token"],
        },
    )
    stored.raise_for_status()

    accepted = client.post(
        "/v1/captures",
        json={
            "object_key": upload["object_key"],
            "sha256": digest,
            "source_kind": "upload",
            "ownership": "owned",
        },
        headers={
            "Idempotency-Key": str(uuid4()),
        },
    )
    accepted.raise_for_status()
    print(accepted.json())
```

## Item operations

```text
GET    /v1/items
GET    /v1/items/{item_id}
GET    /v1/items/{item_id}/image
PATCH  /v1/items/{item_id}
POST   /v1/items/{item_id}/retry
DELETE /v1/items/{item_id}/source
```

User corrections accept only the documented editable fields and are stored with `provenance=user` plus `locked=true`. Subsequent model jobs skip locked values.

Source responses use `Cache-Control: private, no-store`. After source deletion,
the database keeps a tombstone, the bytes return `item_source_not_found`, and
retry returns `source_deleted_not_retryable`; classification, description,
ownership, and other digital-asset fields remain available.

All `/v1/` responses use `Cache-Control: private, no-store` and `Vary: Cookie`.
Upload buffering and image parsing are limited to two concurrent operations and
run outside the async API event loop. The reverse proxy applies the same
connection bound plus a bounded request rate.

Concrete provider and model IDs are stored only for server-side audit. Product
responses expose capability/schema/taxonomy metadata but redact provider and
embedding model identifiers.

## Stable failure behavior

Provider or embedding failures are never replaced with fixed tags:

- `vision_unavailable` becomes a retryable job and finally an `error` Item when retries are exhausted.
- A valid vision result with unavailable embedding becomes `partial`.
- The source Capture remains available until the user explicitly deletes it.
- `POST /v1/items/{item_id}/retry` resumes from the retained immutable Capture.
- To enable the real FashionSigLIP embedding path, rebuild the single worker with
  `STYLECAPTURE_INSTALL_AI_LIGHT=true` and run it with
  `STYLECAPTURE_EMBEDDING_MODE=fashion_siglip`. There is only one capture worker,
  so disabled and real embedding consumers cannot race for the same task.

The generated OpenAPI document at `apps/h5/openapi.json` is the contract source used to generate the TypeScript schema.
