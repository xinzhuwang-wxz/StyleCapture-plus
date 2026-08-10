---
name: doubao-virtual-try-on
description: Generate photorealistic virtual try-on images from one real-person photo and one or more outfit-item collages by calling the Volcengine Ark Doubao Seed 2.0 Lite understanding model and Doubao Seedream 5.0 image API. Use for 真人换装, 穿搭上身, outfit visualization, look-board-to-photo, virtual fitting, or multiple outfits for the same person. Use source-framing-lock batch mode whenever one person receives two or more outfits so the face, body proportions, pose, camera, and crop remain consistent. Never use local image-generation tools for this workflow.
---

# Doubao Virtual Try-On

Create realistic full-body fashion photos from a person reference and outfit boards. Always run the bundled scripts; they are the source of truth for model calls, prompts, retry behavior, and result auditing.

Require Python 3.10 or newer with network access to `ark.cn-beijing.volces.com`. Use only Python standard-library dependencies.

## Required inputs

Collect these semantic inputs:

1. A photo whose primary person is continuously visible from neck and shoulders through both
   knees, with a meaningful segment of both lower legs visible below the knees. Ankles and feet
   are optional. Face sharpness and existing face occlusion are acceptable; the
   workflow must preserve the visible facial features and the occlusion instead of inventing a
   different face. Reject photos cropped above the knees or around the upper thighs.
2. One or more collage or flat-lay images containing the desired garments and optional shoes, bag, belt, jewelry, or other accessories.

Accept an optional third image only as a composition or realism reference. Never treat it as an identity or clothing source.

Use only images the user owns or is authorized to use. If the user says the person is themselves, proceed.

## Choose the workflow

- For exactly one outfit board, run `virtual_try_on.py`.
- For two or more outfit boards for the same person, always run `batch_virtual_try_on.py`. Never launch independent single-look jobs: independent full-body reconstruction causes face, head-size and body-proportion drift.

## Run one outfit

1. Resolve every uploaded image to an absolute local path.
2. Ensure `ARK_API_KEY` is available at runtime. Never paste it into the script, command arguments, logs, skill files, or output metadata. The script prompts securely when run in an interactive terminal and the environment variable is absent.
3. Choose an output directory outside this skill folder.
4. Run:

```bash
python3 <skill-directory>/scripts/virtual_try_on.py \
  "/absolute/path/person.png" \
  "/absolute/path/outfit-board.png" \
  --output-dir "/absolute/path/output"
```

When a target-look example exists, add:

```bash
  --style-reference "/absolute/path/example.png"
```

The default two-attempt limit only performs the second generation when the first audit is not a strict pass. A strict first result returns immediately. Otherwise, select the better audited candidate and return it within the bounded attempt budget. To avoid any automatic paid retry, add `--max-attempts 1`.

5. Read `manifest.json` and `audit-attempt-N.json`. Confirm the selected attempt, scores, missing items, and any artifacts.
6. Visually inspect `result.jpg` before presenting it. Check face identity, item count, garment colors/materials, hands, legs, feet, shoes, bag handles, and background continuity.
7. Return the image with an absolute Markdown image path and summarize the audit scores. Do not claim perfect identity or fidelity beyond the audit and visible evidence.

## Run multiple outfits for one person

Use one call so every look shares the same accepted source-photo framing anchor:

```bash
python3 <skill-directory>/scripts/batch_virtual_try_on.py \
  "/absolute/path/person.png" \
  "/absolute/path/outfit-1.png" \
  "/absolute/path/outfit-2.png" \
  "/absolute/path/outfit-3.png" \
  --output-dir "/absolute/path/output"
```

The batch script must:

1. Analyze exact facial geometry instead of general resemblance.
2. Copy the accepted source photo as the framing anchor; never generate missing anatomy.
3. Reuse the original identity reference plus the same source anchor for every outfit.
4. Lock head pixel size, visible body proportions, pose, lens, camera distance, crop and background.
5. Audit each look against the source face, anchor and outfit board.
6. Cross-audit all final looks side by side.

Treat `cross_look_pass: false` as `needs_attention` even when individual outfits pass. Return the generated looks, read `cross-look-audit.json`, identify outliers, and never present the set as identity- or framing-consistent unless the cross-look audit strictly passes.

Do not infer missing anatomy. When the source does not continuously show the body from neck and
shoulders through both knees and a meaningful segment of both lower legs, stop before generation,
explain which region is cropped, and request
a replacement photo. A face that is soft, partially hidden, covered by glasses, or covered by a
sticker is not by itself a rejection reason.

## Non-negotiable behavior

- Call Ark only through `scripts/virtual_try_on.py` or `scripts/batch_virtual_try_on.py`.
- Use `doubao-seed-2-0-lite-260428` for visual understanding and audit.
- Use `doubao-seedream-5-0-260128` for image generation.
- Never call `image_gen`, another AIGC provider, or a local image model as a fallback.
- Keep the person image as the only identity source and the outfit board as the only replacement-clothing source.
- If an otherwise eligible source reaches the calves or ankles but does not show both feet, skip
  shoes from the outfit board. Never extend the canvas, invent feet, shorten the legs, enlarge the
  head, or reframe the body merely to display footwear.
- Preserve each replacement garment's real silhouette, volume, shoulder line, folds and wearing
  ease. A loose, oversized, boxy, flared or draped item must not become fitted because the source
  garment was tight.
- Preserve target colors from outfit-board pixels, including undertone, relative lightness and
  heather/marl variation. Do not reduce a nuanced warm gray or oatmeal garment to generic white or
  cool gray.
- Use the post-generation audit to rank candidates, trigger the single bounded retry, and record
  diagnostic warnings. Prefer a strict pass, then a review-required result, then the highest-scoring
  generated result. Once Ark has successfully generated an image, do not discard every candidate
  solely because the audit is conservative; return the best candidate with `quality_status` and
  `selected_audit_summary`. Only source-photo ineligibility before generation, provider failure, or
  a missing/invalid generated file blocks delivery.
- Preserve visible shoulder, torso and hip landmarks. When source clothing conceals chest, waist
  or hip width, use conservative neutral continuity from visible landmarks; never infer an
  idealized body or use the loose source garment's outside edge as the person's body contour.
- Keep the generation prompt compact and priority ordered. Let the understanding call return
  structured identity, contour-visibility, color and silhouette facts; never let it author a
  second free-form generation prompt that duplicates the script's deterministic rules.
- Never infer a fresh body independently for each outfit in a same-person set. Reuse the batch identity anchor.
- Do not retain the source photo's clothes or accessories unless the same item appears on the outfit board.
- Generate a single vertical photorealistic image, not a collage, catalog sheet, illustration, or before/after layout.
- Preserve all intermediate JSON and attempt images so failures are diagnosable.
- Reject inflated identity scores based only on gender, ethnicity, hair color or general vibe. Compare exact facial geometry.
- If Ark authentication, permissions, quota, or safety checks fail, report the exact sanitized API error and stop. Do not substitute another generator.

## Troubleshooting

Read [references/api-contract.md](references/api-contract.md) only when changing models/endpoints or diagnosing an Ark request. Common controls:

- `--max-attempts 1`: prevent automatic paid retry.
- `--size 2K`: default output quality.
- `--watermark`: request an API watermark.
- `--understanding-model` or `--image-model`: override only when the user explicitly requests a different Ark model.
