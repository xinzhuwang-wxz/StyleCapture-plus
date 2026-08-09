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

## Preflight and application policy

Before image generation, the understanding call must return machine-readable body coverage,
foot visibility, body-contour visibility, outfit categories, exact color signatures, and garment
silhouette/ease. The script—not the model's prose
alone—then resolves these rules:

- Reject before any paid generation when the person is not continuously visible from neck and
  shoulders through both knees and most of both calves.
- Do not reject for a soft or occluded face. Preserve the visible facial geometry and existing
  occlusion; never beautify or invent hidden features.
- When both feet are not visible, omit requested shoes while preserving the exact source crop and
  body proportions.
- Preserve the target garment's silhouette and wearing ease independently of the source garment.
- Preserve target hue, undertone, relative lightness, and heather/marl variation from outfit-board
  pixels rather than relying on a generic color label.
- For concealed chest, waist, or hip widths, preserve visible skeletal landmarks and use a
  conservative neutral body volume; do not infer an idealized or stereotypical shape.

The understanding model must not return a free-form generation prompt. The script renders a
single compact prompt ordered as person/frame, body volume, target outfit, then output format.

The audit receives the resolved application plan. A result hard-fails when it forces skipped shoes
into frame, reframes/compresses the body for footwear, leaks the source garment's fit, or changes a
loose target garment into a fitted one.

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
2. Accepted source image reused as the body/camera framing lock
3. Outfit-item board

The optional style reference goes only to the understanding request. This prevents its identity or clothes from contaminating generation.

## Generation request shape

```json
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "<deterministic prioritized prompt built from structured analysis>",
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
