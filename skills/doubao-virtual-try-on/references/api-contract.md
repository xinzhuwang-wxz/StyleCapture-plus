# Ark API contract

## Endpoints

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Visual understanding and audit: `POST /chat/completions`
- Multi-reference image generation: `POST /images/generations`
- Authentication: `Authorization: Bearer $ARK_API_KEY`

## Pinned models

- Understanding: `doubao-seed-2-0-lite-260428`
- Generation: `doubao-seedream-5-0-260128`

The user chose these exact model IDs. Do not silently replace them.

## Image transport

Encode local PNG, JPEG, or WebP inputs as data URLs:

```text
data:<mime-type>;base64,<base64-bytes>
```

The generation request uses an ordered `image` array:

1. Person/identity reference
2. Outfit-item board

Batch mode uses:

1. Original person/face reference
2. Canonical full-body identity/body/camera anchor
3. Outfit-item board

The optional style reference goes only to the understanding request. This prevents its identity or clothes from contaminating generation.

## Generation request shape

```json
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "<understanding-model output>",
  "image": ["<person data URL>", "<outfit data URL>"],
  "size": "2K",
  "sequential_image_generation": "disabled",
  "stream": false,
  "response_format": "url",
  "watermark": false
}
```

Expected image responses contain `data[0].url` or, if configured differently, `data[0].b64_json`.

## Retry policy

Retry transient HTTP `408`, `409`, `429`, `500`, `502`, `503`, and `504` responses with short exponential backoff. Never retry authentication or permission failures automatically.

The workflow can perform one quality retry after a completed result fails audit. Append the audit's concrete correction list to the original generation prompt and keep the same two reference images.
