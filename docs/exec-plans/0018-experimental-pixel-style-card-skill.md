# Issue #18: Experimental Pixel Style Card Skill

**Issue:** https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/18

## Goal

Add a small, self-contained Skill that guides an image-capable agent to turn a supplied real-person or outfit photo into a light, coarse-pixel character card for limited creative testing. The Skill must make its experimental, non-core status explicit.

## Scope and boundaries

- Add one documentation-only Skill under `skills/pixel-style-card/`.
- Preserve the input person, outfit, pose, accessories, and meaningful props while giving the card a coarse-pixel treatment.
- Derive an airy icon-stage background from the source scene, outfit palette, and formality.
- Do not add application code, API contracts, providers, model aliases, secrets, dependencies, image assets, generated images, or production workflow integration.
- Do not make a pixel card required for Feed, wardrobe, recognition, outfit planning, purchasing, or `RenderArtifact` correctness.

## Plan of work

1. Add concise `SKILL.md` metadata that triggers on photo-to-pixel-card requests and clearly identifies the limited test use case.
2. Add a deterministic visual workflow: make a source brief, select an adaptive theme, retain the subject, lock coarse pixel clusters, and build a lightweight scene-to-icon background.
3. Add clear rejection criteria for the failure modes observed in exploratory use: fixed sweet/pink motifs, empty flat backgrounds, overly detailed scenery, and fine/painterly pixels.
4. Verify Markdown structure, documentation-only diff, no secrets, and whitespace cleanliness.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source commit / license |
| --- | --- | --- | --- | --- |
| Repository Skill layout | `skills/scene-outfit-matching/SKILL.md` | Adapt layout only | It is the only existing in-repository Skill and establishes the expected `SKILL.md` discovery pattern; this change does not reuse its API-client behavior. | `c3b29c3`, repository source |
| Product pixel-cover implementation | `CONTEXT.md`, `docs/architecture/TECHNICAL-DECISIONS.md`, ADR-0004 | Reject runtime reuse | The proposed Skill is an optional creative prompt guide, not a new or alternate product pixel-provider path. | `c3b29c3`, repository source |
| Local exploratory card guidance | User-provided examples and the local experimental Skill draft | Adapt instructions only | The examples define visual acceptance; no image, code, third-party asset, or provider configuration is copied into this repository. | User-provided material; no redistributed asset/license |

## Progress

- [x] 2026-07-26: Confirmed Issue #18 has no dependency on the product roadmap and is explicitly limited to an experimental Skill.
- [x] 2026-07-26: Audited the existing Skill layout, `_ref/README.md`, product architecture decisions, and repository pixel-cover boundary.
- [x] 2026-07-26: Added the documentation-only Skill with the experimental boundary, coarse-pixel character constraints, source-adaptive icon-stage background, and explicit rejection criteria.
- [x] 2026-07-26: Ran the Skill validator in UTF-8 mode and `git diff --check`; confirmed no image assets or credential-like values were added.

## Verification

- Confirm `skills/pixel-style-card/SKILL.md` has valid frontmatter containing only `name` and `description`.
- Confirm the diff is limited to the Skill and this ExecPlan.
- Run `git diff --check`.
- Scan changed files for credential-like environment variables and generated/binary additions.

## Expected outcome

An agent can use the Skill for a small-scale test or creative exploration with a user-provided image, while maintainers can see immediately that it is not a production feature, provider integration, or dependency of a core user journey.
