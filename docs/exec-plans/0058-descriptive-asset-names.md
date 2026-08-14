# Descriptive wardrobe asset names

## Outcome

Close Issue #98 by making every wardrobe card identify the visible asset rather than its
ingestion source or broad taxonomy. A newly uploaded outfit receives a concise Chinese
title in the existing outfit-analysis request, existing Looks retain a truthful fallback,
and Items reuse their already persisted visual description. Source, category, ownership,
and processing state remain secondary metadata.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Look title generation | Existing LiteLLM outfit-analysis call and `LookAnalysis` JSON; a second LLM request; client-only string truncation | Adapt the existing analysis schema with one `title` field | Produces a grounded title in the same real provider call, adds no latency round trip, and persists provenance with the rest of the analysis | This repository at `3c0fc67`; project-internal, no root license declared |
| Legacy and curated Look names | Existing `SeedLook.title`, `analysis.style`, `analysis.focal_point`; new database column and migration | Reuse `SeedLook.title` and add a version-compatible analysis fallback | Curated titles are already human-reviewed; analysis JSON can evolve without a schema migration while old records remain readable | This repository at `3c0fc67`; project-internal, no root license declared |
| Item names | Existing vision `description`; taxonomy labels; another naming provider | Directly reuse the persisted visual description | The provider already creates appearance-specific Chinese text through the public attribute contract; another inference call or field would duplicate truth | This repository at `3c0fc67`; project-internal, no root license declared |
| UI metadata | Existing `SOURCE_LABELS`, taxonomy labels, card components | Adapt the existing cards and recent-Look entry | Preserves current information architecture while correcting primary/secondary emphasis | This repository at `3c0fc67`; project-internal, no root license declared |

## Progress

- [x] Rebase `codex/descriptive-asset-names` onto latest `pr-target/main` at `9c2c166` (after PR #99).
- [x] Trace curated seeds, live provider attributes, Look analysis persistence, API summaries, and all visible hard-coded names.
- [x] Add backend contract/provider/repository tests for generated, curated, and legacy Look names.
- [x] Add H5 behavior tests for Look and Item card title/metadata placement.
- [x] Implement the minimum vertical slice and regenerate the OpenAPI client contract.
- [x] Run focused backend naming tests, full H5 unit tests, typecheck, Ruff, and mypy.
- [x] Operate the 390x844 wardrobe journey and save look/item/detail screenshots. Visual Verdict: 92.
- [x] Push the independent branch `codex/descriptive-asset-names` from latest `main` (`9c2c166`) and open the second PR. CI confirmation follows the GitHub product job.

## Surprises & discoveries

- The curated corpus already contains high-quality Item `name` values and Look `title`
  values. Item names are persisted as `description`; Look titles were stored only as the
  semantic `focal_point`, then hidden by a source-derived frontend title.
- Live item recognition already emits a Chinese `description`, so the Item defect is a
  presentation bug rather than a missing AI capability.
- Look analysis is persisted as versioned JSON and is present on list-domain objects.
  A new title therefore needs neither a database migration nor an extra provider call.

## Decision log

- Add an optional title field to `LookAnalysis` so records produced before this change
  remain readable. Prefer the title, then the existing style description, then a neutral
  processing fallback when constructing the Product API `display_name`.
- Require a concise four-to-six-character Chinese title from the existing LiteLLM call.
  Preserve longer human-reviewed curated titles as authored rather than destructively
  truncating meaningful names.
- Use Item `description` verbatim as the primary label and keep the normalized category
  in secondary metadata. Do not add a parallel Item naming field.
