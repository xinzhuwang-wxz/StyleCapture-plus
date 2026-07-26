# Real Photo Flat-Lay Collage Skill ExecPlan

**Goal:** Let a user request a clean, private 3:4 pure-white flat-lay collage from a real photo that has already entered StyleCapture's Capture → Item → Look workflow.

**Scope:** Add a Product-API-only Skill and change the deterministic collage renderer's default canvas from a square warm-white image to a pure-white 3:4 image. Do not introduce a second image upload API, a second garment-recognition path, provider access from the Skill, or generated garment facts.

## User-visible flow

1. A user captures or uploads an authorized real outfit/garment photo through the existing flow.
2. Existing capture and look processing produce owned, ready Item display assets and a Look.
3. The Skill requests `POST /v1/looks/{look_id}/renders` with `kind=collage` and an idempotency key.
4. The existing RenderArtifact worker makes a deterministic, private PNG from those real Item display assets.
5. The H5 Look detail and the Skill retrieve only the authenticated artifact route after it succeeds.

The output is a presentation derivative, not a new source of truth: it cannot add clothing, replace Item data, claim a provider result, or survive a missing source asset by inventing content.

## Rendering contract

- Canvas: 768×1024 pixels, portrait 3:4.
- Background: opaque pure white `#FFFFFF`.
- Layout: the existing one-to-six independent Item grid, padded and with consistent gaps.
- Source: only ready Item `display_object_key` assets (falling back to an available source asset as the existing processor permits).
- Privacy: private `RenderArtifact` image route; it is not the shareable pixel cover.

## Integration boundaries

| Layer | Responsibility | Explicit non-responsibility |
| --- | --- | --- |
| Capture / Look | Own real image provenance, consent, segmentation, recognition and Item readiness | Do not render a presentation collage |
| Render feature | Own idempotency, queueing, cache signature, deterministic Pillow rendering, object storage and failure state | Do not change the underlying clothes |
| Skill | Request and poll the versioned Product API for an existing Look | Do not accept raw image bytes, call LiteLLM, copy prompts or expose provider details |
| H5 | Display the returned artifact and its pending/failed states | Do not recreate the collage in the browser |

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source commit / license |
| --- | --- | --- | --- | --- |
| Artifact lifecycle | Existing `render` feature and `/v1/looks/{look_id}/renders` | Direct reuse | Already owns Look-based idempotency, queueing, private image streaming and failure semantics | `87dd81c`; project code |
| Flat-lay composition | Existing `PillowLookCollageRenderer` | Adapt | Existing renderer already composes one-to-six real Item images deterministically; only format and background change | `87dd81c`; Pillow HPND |
| Skill facade | `skills/scene-outfit-matching` | Adapt | Existing Skill proves the required Product-API-only boundary and Node test pattern | `87dd81c`; project code |
| Image generation | LiteLLM image capability | Rejected | A predictable collage of real Item assets must not invent or alter garments | Existing project architecture |

## Verification

- Run `npm test` in `skills/real-photo-flat-lay-collage`.
- Run `uv run pytest services/backend/tests/render/test_collage.py -q`.
- Run the existing render API tests and one real H5 Look journey: captured photo → ready Look → queued → succeeded collage → authenticated image.
- Inspect the resulting PNG dimensions, pure-white corner pixels, private artifact route, and missing-source failure behavior.
