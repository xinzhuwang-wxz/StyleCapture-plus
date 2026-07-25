# Doubao Seed 2.0 Mini vs Lite — live A/B

> 最终产品决策（2026-07-26）：保留下方 A/B 实测作为历史证据，但按产品负责人要求，`outfit_analysis` 正式路由已切回 Lite，以优先保证演示质量与全链路一致性；Mini 不再承担运行时主路由。

- Run UTC: `2026-07-25T21:10:21.632156+00:00`
- Gateway: local LiteLLM; serial requests; zero retries
- Corpus: 3 real item images + 3 real Look images + 3 scene requests per model
- Seedream/image generation: unchanged and not invoked
- Mini mechanical gate: **未通过**

| Model | Success | Quality /100 | Median ms | P95 ms | Schema | Chinese | Est. CNY |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lite | 9/9 | 100.0 | 21310 | 28040 | 100% | 100% | 0.040268 |
| Mini | 9/9 | 87.8 | 8703 | 13479 | 100% | 100% | 0.025360 |

## Decision metrics

- Quality delta (Mini - Lite): -12.2 points
- Median latency delta (Mini - Lite): -12607 ms
- Estimated cost saving: 0.37

## Capability routing

| Capability | Lite quality | Mini quality | Lite mean ms | Mini mean ms | Recommendation |
| --- | ---: | ---: | ---: | ---: | --- |
| garment_understanding | 100.0 | 73.3 | 21473 | 11615 | keep_lite |
| outfit_analysis | 100.0 | 100.0 | 19737 | 8725 | mini_with_lite_fallback |
| outfit_reasoning | 100.0 | 90.0 | 19143 | 7142 | keep_lite |

- `vision_understanding`: keep Lite. Mini misclassified the pale-green cardigan
  as `tops/knitwear` instead of the required `outerwear/cardigan` taxonomy pair.
- `outfit_analysis`: Mini is acceptable for this bounded descriptive route; use
  Lite as fallback on provider, schema, or Chinese-completeness failure.
- `reasoning`: keep Lite. Mini ranked the casual denim/sneaker plan above the
  business plan for the formal interview request.
- `visual_grounding`: keep Lite because this run did not evaluate box/region quality.
- `image_generation`: keep Seedream; it was deliberately not part of this A/B.

## Historical A/B recommendation

The capability-specific recommendation produced by this A/B was:

- product code calls only `outfit_analysis`; the gateway maps it to Mini;
- on a provider failure, invalid structured response, or non-Chinese user-facing
  response, the same adapter calls server-only `outfit_analysis_fallback` (Lite);
- attempts are strictly sequential, and a valid Mini response ends the call without
  invoking Lite;
- product metadata continues to expose `outfit_analysis`, never a provider or model ID;
- `vision_understanding`, `visual_grounding`, and `reasoning` remain on Lite, while
  `image_generation` remains on Seedream.

The current production-shaped routing supersedes this recommendation: product code still
calls only the stable `outfit_analysis` capability alias, while LiteLLM maps that alias to
`doubao-seed-2-0-lite-260428`.

## Interpretation limits

Quality is a deterministic rubric over expected taxonomy, visible-evidence terms,
closed candidate preservation, and expected top rank. It is not a broad human-style
preference score. Three cases per capability are enough for a routing smoke, not a
production-wide quality guarantee.

Detailed per-call outputs and checks are in the adjacent sanitized JSON result.
The routing decision is capability-specific; the overall Mini gate remains failed and
does not justify replacing Lite for the other capabilities.

Pricing source: https://www.volcengine.com/docs/84458/1585097?lang=zh&redirect=1
