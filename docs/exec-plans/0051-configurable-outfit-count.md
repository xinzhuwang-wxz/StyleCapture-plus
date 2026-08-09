# Configurable AI Outfit Count

## Goal

Let a user request either three or four AI outfit recommendations through the
existing wardrobe-first Product API workflow. The selected count must flow from
H5 through FastAPI, deterministic candidate generation, LiteLLM reranking,
streaming responses, workflow traces, and the generated OpenAPI client.

## Reuse Audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
|---|---|---|---|---|
| Wardrobe inventory and outfit curation | `C:\Users\hjq15\wardrobe\.agents\skills\generate-outfits` | Adapt principles only | Reuse count-first UX, unique combinations, garment-use balance, color/silhouette/layering guidance; do not copy its local JSON workflow | Local user-provided skill |
| Outfit planning | Existing `features/outfit` vertical module | Direct reuse | It already owns wardrobe recall, deterministic hard rules, LiteLLM reranking, streaming, traces, replacement, and Look saving | Repository code |
| H5 recommendation journey | Existing `AIRecommendScreen` and generated Product API client | Direct reuse | Add one compact count control and one generated contract field; no parallel request shape | Repository code |

## Plan

1. Add failing Product API and H5 tests for selecting three plans while keeping
   four as the default.
2. Add `plan_count` to the domain request and `outfit_count` to the HTTP contract.
3. Make deterministic plan generation and validation honor the requested count.
4. Include the requested count and adapted curation guidance in the LiteLLM
   reranker input without allowing it to alter closed candidates.
5. Regenerate the OpenAPI TypeScript contract and wire the H5 segmented control.
6. Run focused backend/H5 tests, full type/build checks, then verify the real
  mobile flow against the local Docker stack.
## Decisions

- Support exactly 3 or 4 plans. This matches the current PRD and avoids silently
  widening the Product API beyond the tested wardrobe diversity contract.
- Keep modeled image generation outside the synchronous recommendation path.
  Saved Looks may continue to schedule RenderArtifacts through the existing
  presentation workflow.
- The backend owns count validation and candidate uniqueness. H5 only expresses
  the user's selection.

## Surprises & Discoveries

- The repository already implements most of the referenced skill's useful
  workflow: real wardrobe recall, unique closed candidates, wardrobe gaps,
  LiteLLM explanations, replacement, Look saving, and truthful degradation.
  The work is therefore an enhancement, not a second recommender.
