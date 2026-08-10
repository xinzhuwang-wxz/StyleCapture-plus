# Audited virtual try-on identity preservation

## Goal

Make the H5 `look.virtual_try_on` product capability execute the repository's
`doubao-virtual-try-on` Skill instead of the former one-shot product image-edit path. The
generated image may change the outfit, but it must preserve the same identifiable person.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason |
| --- | --- | --- | --- |
| Product try-on shell | `render/processing.py`, RenderArtifact storage and signatures | Reuse | Keep authorization, jobs, persistence, privacy and honest degradation. |
| Audited try-on workflow | `skills/doubao-virtual-try-on` | Direct runtime reuse | It already owns analysis, generation, audit and correction retry. |
| Cache invalidation | `render/signatures.py` | Reuse | Put the Skill version in the input signature so older images are not reused. |

## Decisions

1. Standard Compose Workers configure only the audited Skill executor for product try-on.
2. The selected user photo is the only identity source; a deterministic collage of current Item
   images is the only outfit source.
3. The Skill explicitly locks face geometry, age, skin tone, glasses, hair and other identity
   markers, and forbids beautification or face reshaping.
4. A valid generated candidate is stored even when the audit is conservative. Audit results rank
   the bounded candidates and are persisted as `pass`, `review_required`, or `needs_attention`;
   source-photo rejection, provider failure, and a missing/empty/invalid image still degrade to the
   real Item collage without entering the old LiteLLM/FASHN execution path.
5. Skill version `1.4.3` participates in the RenderArtifact input signature.
6. The understanding step is a hard preflight: it rejects photos cropped before the calves, but
   does not reject soft or occluded faces. Visible facial geometry and existing occlusion remain
   immutable identity evidence.
7. A neck-through-calves photo remains eligible when feet are outside the frame. In that case the
   resolved application plan omits requested shoes instead of inventing feet or compressing legs.
8. Target garment silhouette and wearing ease are audited independently from the source garment;
   fitted source clothes must not make a loose target garment fitted.

## Verification plan

- Contract-test exact-person constraints and the identity audit threshold.
- Test the subprocess adapter's secret boundary, hard-pass gate and trace metadata.
- Test that the audited executor takes precedence, returns the best valid candidate after a
  conservative audit, and degrades only for preflight/provider/file failures without calling the
  old executor.
- Run targeted backend tests, formatting, linting and type checks.
- Leave paid real-image visual acceptance to an explicit user-triggered UI retry.

## Progress

- [x] Locate the real H5-to-Worker execution path.
- [x] Replace its configured generator with the repository Skill workflow.
- [x] Strengthen identity constraints, audit threshold and pipeline version.
- [x] Add adapter and processing contract tests.
- [x] Reject insufficient body framing before generation and return the specific reason to H5.
- [x] Add deterministic footwear omission and target-silhouette audit rules.
- [x] Keep the best valid generated candidate when audit scores are conservative; persist the
  selected attempt, quality status and compact audit summary in provider trace.
- [x] Validate the generated image signature and preserve its actual JPEG/PNG/WebP content type.
- [x] Accept both `STYLECAPTURE_ARK_API_KEY` and `ARK_API_KEY` in Compose so the existing local
  product-prefixed secret is not silently replaced with an empty Worker/LiteLLM value.
- [x] Complete targeted 1.4.3 automated verification: 14 Skill tests, 31 render tests and Ruff pass.
- [x] Recreate LiteLLM and Worker after the Compose secret-alias fix; both non-sensitive Ark
  configured booleans are true and the Worker reports the 1.4.3 pipeline.
- [x] User verifies one authorized real reference photo from the H5 flow. The 1.4.3 candidate is
  delivered successfully with materially improved body proportions; face identity remains the
  next focused quality issue.

## Validation notes

- The complete backend suite cannot collect under native Windows because the existing local object
  store imports Unix-only `fcntl`; the same platform limitation also produces four pre-existing
  full-tree mypy errors. The changed render/config modules pass focused mypy.
- Docker Compose YAML parses with the Ark key present in both Worker profiles, and the versioned
  Skill package validates successfully.
- No paid Ark generation was triggered during implementation or automated verification.
- Rebuilt API, LiteLLM and Worker report healthy. The Worker uses
  `doubao-virtual-try-on-skill-v1.4.3`; API 8002 and both H5 proxy checks return HTTP 200. The
  non-sensitive Worker/LiteLLM Ark configured booleans are true after the secret-alias recreate.
- H5 typecheck, the four try-on photo-picker tests, and the production build pass. The full H5
  suite has six unrelated existing failures in `feed-runtime.test.tsx`; no try-on test failed.
- The 2026-08-10 real H5 run succeeded in about 229 seconds with `quality_status=needs_attention`,
  `selected_attempt=1`, identity 83, body 91, outfit 88, photorealism 92, natural head/body ratio,
  no vertical compression, and preserved target silhouette/ease. The audit explicitly reports
  changed facial features and recommends restoring the source face geometry and natural texture.
  Further identity work is deferred to a focused follow-up rather than adding more prompt clauses
  under the current deadline.

## User evidence and correction

Testing showed two failure classes that a generic "full body" instruction did not cover. First,
the generator shortened the legs to force shoes into a source photo that ended at the calves.
Second, it copied the tight source top's outline onto a loose replacement top. Version 1.4.0 makes
both cases explicit application-policy and hard-audit failures rather than best-effort prose.

Follow-up testing found that stacking a model-authored generation prompt with deterministic rules
created long, repetitive instructions and still allowed color and torso-volume drift. Version
1.4.1 makes the understanding call return only structured contour visibility, target color and
silhouette facts. The script now emits one compact priority-ordered prompt. Concealed chest, waist
and hip widths use conservative neutral continuity rather than a stereotypical body inference.
This iteration intentionally does not add new fine-grained structure-audit thresholds; it first
isolates the effect of the clearer generation contract while retaining the existing general audit.

Version 1.4.3 separates delivery from the strict audit threshold. Real testing showed that the
provider could generate a useful try-on and then lose it because a conservative audit returned a
single failing flag. The strict tier remains preferred and triggers early return; otherwise one
bounded retry is allowed, candidates are ordered by strict pass, review eligibility and score, and
the best valid image is delivered with diagnostic metadata. This favors a visible, auditable
candidate over an unnecessary collage while keeping input, provider and file-integrity failures as
hard blockers. ADR-0008 records this product-level change.
