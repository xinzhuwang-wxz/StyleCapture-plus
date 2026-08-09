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
4. Only a Skill manifest with `hard_pass=true` is stored as a successful try-on. Otherwise the
   RenderArtifact honestly degrades to the real Item collage and never falls back to the old
   LiteLLM/FASHN execution path.
5. Skill version `1.4.1` participates in the RenderArtifact input signature.
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
- Test that the audited executor takes precedence and that audit failure degrades without calling
  the old executor.
- Run targeted backend tests, formatting, linting and type checks.
- Leave paid real-image visual acceptance to an explicit user-triggered UI retry.

## Progress

- [x] Locate the real H5-to-Worker execution path.
- [x] Replace its configured generator with the repository Skill workflow.
- [x] Strengthen identity constraints, audit threshold and pipeline version.
- [x] Add adapter and processing contract tests.
- [x] Reject insufficient body framing before generation and return the specific reason to H5.
- [x] Add deterministic footwear omission and target-silhouette audit rules.
- [x] Complete targeted automated verification: 38 tests, Ruff and focused mypy pass.
- [ ] User verifies one real reference photo from the H5 flow.

## Validation notes

- The complete backend suite cannot collect under native Windows because the existing local object
  store imports Unix-only `fcntl`; the same platform limitation also produces four pre-existing
  full-tree mypy errors. The changed render/config modules pass focused mypy.
- Docker Compose YAML parses with the Ark key present in both Worker profiles, and the versioned
  Skill package validates successfully.
- No paid Ark generation was triggered during implementation or automated verification.

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
