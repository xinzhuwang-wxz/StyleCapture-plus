# Doubao model-routing A/B

This evaluator compares the server-only Lite and Mini candidate aliases through the
local LiteLLM gateway. It reuses the production prompt, schema, taxonomy, and parsing
code for:

- single-garment vision tagging;
- whole-outfit relationship analysis;
- closed-candidate scene/outfit reranking.

Seedream is deliberately excluded. The run is serial (`max concurrency = 1`) and
uses three real item images, three real Look images, and three reasoning requests per
model. No image bytes, data URLs, credentials, request headers, or raw provider
responses are written to disk.

## Run

The local `litellm` service must contain the candidate aliases from
`config/litellm.yaml` and have `ARK_API_KEY` injected server-side.

```bash
docker compose build litellm
docker compose up -d --no-deps --force-recreate litellm

uv run --project services/backend python evals/model-routing/run_ab.py \
  --output evals/model-routing/results/doubao-mini-vs-lite-2026-07-26.json \
  --report evals/model-routing/REPORT.md

uv run --project services/backend python evals/model-routing/validate_result.py \
  evals/model-routing/results/doubao-mini-vs-lite-2026-07-26.json \
  .omx/specs/autoresearch-model-routing/result.json
```

The gateway key is read from `STYLECAPTURE_EVAL_GATEWAY_KEY`, then
`LITELLM_MASTER_KEY`, with the repository's local-only Compose default as the final
fallback. The value is never logged or stored.

## Cost assumptions

Estimated cost uses the official Ark 0–32k token tier current on 2026-07-26:

| Model | Input, CNY / 1M tokens | Output, CNY / 1M tokens |
| --- | ---: | ---: |
| Doubao Seed 2.0 Lite | 0.60 | 3.60 |
| Doubao Seed 2.0 Mini | 0.20 | 2.00 |

Source: [Volcengine Ark model pricing](https://www.volcengine.com/docs/84458/1585097?lang=zh&redirect=1).
Image accounting follows the provider-reported prompt token usage; estimates do not
attempt to reconstruct image-token metering locally.

## Production decision

The approved routing keeps every product-facing capability name stable. Only
`outfit_analysis` maps to Mini. Its server adapter invokes the Lite-backed,
server-only `outfit_analysis_fallback` alias sequentially when Mini has a provider
failure, violates the response schema, or fails the Simplified-Chinese output
contract. A valid Mini response never triggers the fallback. All other text/vision
aliases remain on Lite, and image generation remains on Seedream.
