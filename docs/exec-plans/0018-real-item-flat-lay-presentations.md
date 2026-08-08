# Real Item Flat-Lay Presentations ExecPlan

**Goal:** For every newly captured outfit, produce one private pure-white 3:4 image for each resolved Item and use it as the Item-detail hero without rewriting historical Items or replacing source evidence.

## Observable outcome

1. Each new Item is queued for `flat_lay_item` as soon as Capture processing marks it ready; the job does not wait for or derive from a Look collage.
2. A genuine transparent `refined_mask` may be placed on a 1728×2304 white canvas with Pillow. An opaque rectangle, coarse polygon, missing cutout, or other unreliable display asset must use the original Capture image through the configured `image_generation` capability.
3. Both paths pass the same release gate: exact 1728×2304 dimensions, at least 90% near-white border pixels, and at least 50% pure-white canvas. Failed output is never published as the Item hero.
4. In `按单品 → 单品卡片 → 单品详情页`, queued/running generation shows the authenticated original image blurred under a spinner and “正在生成单品图”. Success replaces it automatically with the generated white-background image; failure retains the existing display fallback. The separate `按穿搭 → 穿搭详情页` hero is not changed by this feature.
5. Existing historical Items are not batch reprocessed. Source and existing display assets remain immutable.

## Progress

- [x] Reworked the backend presentation processor into the refined-mask/Pillow plus original-image/hosted-generation hybrid.
- [x] Added the 1728×2304 white-background release gate and provider-path trace data.
- [x] Added new-Capture scheduling for upload, Feed selection, and whole-outfit component paths.
- [x] Reworked Item detail generation, blurred-original progress, automatic success replacement, and failure fallback.
- [x] Changed the Skill to request each Item presentation directly, without creating or cropping a Look collage.
- [x] Ran a real Doubao/Seedream sample from the supplied outfit: blouse, skirt, and shoes were independently produced at 1728×2304 and passed the product gate.
- [x] Added backend, scheduler, Skill, H5 behavior, static, and capture-regression coverage.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
|---|---|---|---|---|
| Asynchronous private Item image | Existing `item_presentation` feature | Adapted reuse | Already owns Item-scoped idempotency, state, storage, retry, and authenticated delivery. | This repository |
| Reliable cutout composition | Existing `PillowLookCollageRenderer` | Direct reuse only for transparent `refined_mask` | Pillow is deterministic and high fidelity when the input already has real alpha; it cannot turn an opaque rectangular screenshot into a cutout. | This repository; Pillow HPND |
| Unreliable/missing cutout recovery | Existing `LiteLLMImageGenerator` and `image_generation` alias | Adapted reuse | Preserves the single server-side provider boundary and uses the original Capture evidence rather than a fake local crop. | This repository; LiteLLM MIT |
| Private original fallback | Existing `/v1/items/{id}/source` and `useDisplayImage` | Adapted reuse | Shows honest source evidence during generation without introducing a second media path. | This repository |
| Item discovery | Existing Capture/Look decomposition | Direct reuse | The worker already resolves Item identity and attributes; the Skill must not duplicate vision understanding. | This repository |

## Verification

- `uv run --package stylecapture-backend pytest services/backend/tests/item_presentation/test_item_presentation_processing.py services/backend/tests/item_presentation/test_item_presentation_scheduler.py -q` → 5 passed.
- `uv run --package stylecapture-backend pytest services/backend/tests/worker/test_capture_processing.py services/backend/tests/worker/test_feed_selection_processing.py services/backend/tests/worker/test_whole_outfit_processing.py -q` → 27 passed.
- `uv run --package stylecapture-backend ruff check ...` → passed on changed backend and Item-presentation tests.
- H5 `tsc -b --noEmit` → passed.
- Focused H5 Item-detail tests → passed, including the direct `按单品` entry, `/source`, blur/loading state, generation marker, and Item-over-Look layer ordering.
- `node --test skills/generate-outfit-item-assets/tests/render.test.js` → 2 passed.
- Skill Creator `quick_validate.py` → valid.

## Surprises & discoveries

- The previous Pillow path only placed an opaque rectangular display crop on a white canvas. It was visually a screenshot, not a cutout, even though the canvas itself was 3:4.
- A display asset is usable for deterministic composition only when its segmentation provenance is `refined_mask` and the encoded image contains meaningful alpha transparency.
- Full-outfit overlaps can make an image model transfer a strap or tie to the wrong garment. The generation constraint now assigns overlapping parts to their owner and permits only conservative material continuation under occlusion.

## Decision log

- 2026-08-08: Keep `flat_lay_item` separate from source and display assets; a successful derivative is the Item-detail hero but never new source evidence.
- 2026-08-08: Remove the collage prerequisite. New resolved Items queue their independent presentation directly.
- 2026-08-08: Use Pillow only for verified refined-alpha cutouts; otherwise use the original Capture through the existing hosted image-generation capability.
- 2026-08-08: Do not run a wardrobe-wide historical backfill. The automatic scheduler is attached only to new Capture completion paths.
- 2026-08-08: Product acceptance is scoped to the Item detail opened from `按单品`; the Look-detail hero remains a separate surface.
