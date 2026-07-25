# Autoresearch mission: Doubao Seed 2.0 Mini vs Lite routing

## Decision to make

Determine whether `doubao-seed-2-0-mini-260428` is a safe lower-cost default for
StyleCapture's low-risk structured AI capabilities while preserving Lite as a quality
fallback. Image generation is explicitly out of scope and remains on Seedream.

## Required live evidence

- Call both candidates through the local LiteLLM gateway, serially with no retries.
- Exercise the production garment-understanding prompt/schema on three different real
  item images.
- Exercise the production whole-outfit prompt/schema on three different real Look
  images.
- Exercise the production closed-candidate outfit reranker on three different scene
  requests.
- Record wall latency, provider-reported token usage, estimated cash cost, errors,
  JSON/schema validity, taxonomy validity, Chinese completeness, and bounded semantic
  quality checks without storing credentials or image bytes.
- Do not change any stable product alias until the evidence is approved.

## Pass gate for recommending Mini

- 9/9 Mini requests succeed with zero schema/taxonomy/Chinese contract errors.
- Each capability has a mean quality score of at least 85/100.
- Overall Mini quality is no more than 5 points below Lite.
- Mini estimated token cost is lower than Lite on the official 0-32k price tier.
- Latency is reported, not assumed; a slower Mini may still be rejected for an
  interactive route even if it is cheaper.

The evaluator script owns the mechanical pass/fail verdict. The report may make a
more conservative per-alias routing recommendation when a capability-specific metric
is marginal.
