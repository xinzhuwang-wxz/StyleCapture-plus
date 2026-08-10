# ADR-0008: Deliver the best valid audited try-on candidate

- Status: Accepted
- Date: 2026-08-10
- Supersedes: ADR-0007 decision 4

## Context

The 1.4.1 product integration required `hard_pass=true` before a generated try-on could be stored.
Real H5 testing showed that Ark could successfully generate a useful try-on while the subsequent
vision audit conservatively failed one or more identity, body, or garment checks. The Worker then
discarded every generated image and degraded to a real-item collage, so users repeatedly saw an
audit failure instead of the candidate they had paid and waited for.

The audit is still valuable for bounded correction, ranking, diagnostics, and later quality
improvement. It is not reliable enough to be the sole delivery gate after a valid image has already
been generated.

## Decision

1. The source-photo coverage preflight remains a hard gate before paid generation. Photos must show
   the person continuously from neck and shoulders through both knees, with a meaningful segment
   of both lower legs; ankles and feet are optional.
2. Generate at most two candidates by default. Return immediately on a strict first-attempt pass;
   otherwise use the first audit's corrections for one retry.
3. Rank candidates by strict pass, review eligibility, and aggregate score. A valid generated image
   is always delivery eligible even when all candidates still need attention.
4. Persist `selected_attempt`, `hard_pass`, `audit_release_eligible`, `delivery_eligible`,
   `quality_status`, and a compact selected-audit summary in the provider trace.
5. Use `pass`, `review_required`, and `needs_attention` to distinguish strict quality from usable or
   risky delivery. These labels are diagnostic evidence, not claims of physically accurate fit.
6. Continue to block and degrade to the real-item collage when the input preflight rejects the
   photo, the Ark/API/network call fails, or the generated file is missing, empty, or has an invalid
   JPEG/PNG/WebP signature.
7. Do not enter the legacy LiteLLM/FASHN execution path when the configured Skill returns a valid
   candidate.

## Consequences

- Users receive a generated try-on whenever generation itself succeeds, instead of losing all
  candidates to a conservative post-generation judge.
- Some delivered candidates can have visible quality risks. The trace makes those risks measurable
  and supports focused prompt or threshold tuning without hiding the image.
- At most one automatic retry bounds provider cost and expected waiting time.
- The render pipeline version moves to `doubao-virtual-try-on-skill-v1.4.3`, invalidating older
  cached results.

## Verification

- Skill tests cover source rejection, strict pass, review eligibility, and delivery of a
  `needs_attention` candidate.
- Provider tests cover trace metadata, actual output content type, and invalid image rejection.
- Render processing and signature tests cover the 1.4.3 product contract.
- A user-authorized H5 run remains required for visual acceptance and latency evidence.
