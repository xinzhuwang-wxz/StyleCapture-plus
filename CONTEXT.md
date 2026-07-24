# Domain Language

Use these terms consistently in code, APIs, tests, Issues, and ADRs.

| Term | Meaning |
|---|---|
| Capture | Immutable evidence of an input event: upload, camera image, Feed frame, timestamp, lasso path, and source provenance. |
| Item | The canonical digital representation of one garment or accessory. It holds visible facts, inferred attributes, confidence, ownership state, and source links. |
| Look | A saved outfit relationship referencing Items. It may originate from Feed, upload, or AI generation and never duplicates Item facts. |
| OutfitPlan | A proposed complete combination with slots, constraints, explanations, owned Items, and missing slots. It becomes a Look only when saved. |
| RenderArtifact | A derived collage, try-on, pixel cover, or later animation tied to exact input versions and provider evidence. |
| PreferenceSignal | An event expressing taste or behavior, such as save, reject, reason chip, replacement, or purchase. It does not mutate garment facts. |
| CommerceOffer | Time-varying purchasable information linked to an Item or missing slot. It is not the Item itself. |
| OwnershipState | `owned`, `collected`, `wanted`, `purchased_pending`, or another explicitly versioned state. |
| ProcessingState | `accepted`, `processing`, `ready`, `partial`, `error`, or `deleted`; clients must render these honestly. |
| Product API | Versioned domain interface shared by H5, Skill/Agent, internal tooling, and future authorized clients. |
| Provider | Replaceable adapter for VLM, segmentation, embedding, try-on, pixel generation, storage, or commerce capability. |
| CuratedSeed | Manually reviewed Feed metadata used for demo browsing and deterministic regression; never evidence of a runtime model call. |

## Invariants

- Capture is evidence; Item is the canonical garment asset; Look is a relationship.
- A visual similarity suggestion never proves two Items are identical.
- Manual values outrank later automatic enrichment.
- Owned and aspirational preference signals have different recommendation roles.
- Provider-specific names and payloads do not leak through Product API contracts.
- Runtime model calls go through LiteLLM aliases; only infrastructure adapters know concrete provider identifiers.
- `curated_seed` annotations and live model observations are different provenance classes and cannot be silently converted into one another.
- A generated image is a RenderArtifact, never evidence that an Item exists or is owned.
- Runtime fallbacks are explicit product states, never fabricated success.
