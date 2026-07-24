# ADR-0001: LiteLLM model gateway and curated Feed seed data

- Status: Accepted
- Date: 2026-07-25

## Context

The demo needs a varied Feed corpus before runtime AI integration is economical, while user-triggered visual understanding, outfit reasoning, and image generation must remain genuine product capabilities. Direct provider calls scattered through UI, domain, or workers would make model changes difficult and blur the line between curated demo metadata and live AI output.

## Decision

1. Application code uses LiteLLM as the single language/vision model gateway. Product modules depend on capability contracts and stable aliases, never Volcengine request payloads or model IDs.
2. Initial aliases are:
   - `reasoning`: the Ark endpoint/deployment injected as `ARK_REASONING_ENDPOINT_ID`.
   - `vision_understanding`: `doubao-seed-2-0-lite-260428`.
   - `image_generation`: `doubao-seedream-5-0-260128`.
3. The provider adapter owns LiteLLM configuration, retries, timeouts, response normalization, tracing, and schema validation. Image generation may use a provider-specific transport behind the same application contract if LiteLLM support is incomplete; this must be decided by a live contract test, not by leaking the difference into business code.
4. Credentials are injected server-side through environment or secret management. `VOLCENGINE_API_KEY` and equivalent credentials must never enter the repository, browser bundle, fixture corpus, trace payload, or log.
5. The initial Feed library may be tagged manually by the development agent. Every such annotation is stored as `provenance = curated_seed`, includes source and review metadata, and is never represented as a provider response.
6. New user uploads, camera images, uncached Feed selections, outfit reasoning, and generated images use real runtime provider calls when the corresponding feature is enabled. Codex does not provide runtime intelligence.
7. At least one uncached, traceable live request per enabled capability is required for milestone acceptance. Automated tests may use fakes only through the public capability contracts.

## Consequences

- Demo browsing and deterministic regression do not consume model quota.
- Curated examples cannot prove runtime AI quality; live smoke evidence remains mandatory.
- Providers and model versions can change without rewriting domain or UI code.
- A temporary provider limitation becomes an adapter concern or an explicit product state, not a hidden mock.

## Rejected alternatives

- Bulk pre-tagging the entire demo Feed through paid APIs: unnecessary cost for known seed content.
- Treating manual labels as cached AI results: misleading provenance and invalid evaluation evidence.
- Calling Doubao/Ark directly from features or workers: provider lock-in and duplicated error handling.
- Letting Codex generate product-time classifications or outfit answers: the shipped product would not contain the claimed intelligence.

## Verification

- Static architecture tests reject provider imports outside the infrastructure adapter.
- Configuration tests confirm model aliases resolve without exposing secrets.
- Feed fixtures expose `curated_seed` provenance in data and traces.
- Live smoke tests record provider, model, schema, latency, and uncached status without storing secret material.

## References

- [Volcengine Ark API quick start and OpenAI-compatible endpoint](https://www.volcengine.com/docs/82379/1795150)
- [Volcengine Seedream API documentation](https://www.volcengine.com/docs/82379/seedream?lang=zh)
- [Volcengine release notes confirming the selected Seed 2.0 lite and Seedream 5.0 model versions](https://www.volcengine.com/docs/6492/2165228?lang=en)
