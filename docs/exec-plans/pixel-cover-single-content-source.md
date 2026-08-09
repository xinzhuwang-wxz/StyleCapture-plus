# Pixel cover single-content-source correction

## Goal

Prevent outfit Items from being copied into pixel-card backgrounds by ensuring that a render has
exactly one content image: the original Look image, an explicitly selected completed try-on, or a
collage only when neither person image exists.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason |
| --- | --- | --- | --- |
| Pixel-card rendering | Existing `RenderProcessor` and `pixel-character-card` contract | Adapted reuse | Keep the provider, style references, storage and sprite pipeline; correct only content-source selection. |
| Original Look source | `Look.display_object_key` | Direct reuse | It already stores the selected video frame or uploaded outfit image. |
| Try-on source | Explicit `source_artifact_id` contract | Direct reuse | It already restricts the source to a completed try-on from the same Look. |
| Cache invalidation | Render prompt/pipeline version in `signatures.py` | Direct reuse | A version bump prevents old multi-source artifacts from being returned as cache hits. |

## Decisions

1. Exactly one content image is passed to pixel generation.
2. A completed try-on explicitly selected by the client is used alone.
3. Otherwise the original Look display image is used alone.
4. The generated Item collage is used alone only when the Look has no original display image.
5. The two bundled style anchors remain style-only inputs and never carry this Look's Items.
6. Provider traces record the resolved source kind and content-image count.

## Verification plan

- Test original-image, try-on-image and collage-only input paths.
- Assert every path passes exactly one content image plus two fixed style anchors.
- Assert the version bump participates in the RenderArtifact signature and invalidates v10 output.
- Run targeted render tests, Ruff and focused type checking.

## Progress

- [x] Confirm PR 76 is merged and its prompt prohibition remains in `main`.
- [x] Identify the multi-content input bug in `_process_pixel_cover`.
- [x] Implement deterministic single-content source selection and trace metadata.
- [x] Restore the Skill, shared style contract and pixel-trial behavior to their pre-PR-76 state.
- [x] Complete automated verification: 51 tests, Ruff and focused mypy pass.
- [ ] Merge the PR.

## Surprises & discoveries

PR 76 correctly prohibited floating outfit Items in prose, but the collage path still supplied both
the original Look image and the generated Item collage. The collage's isolated objects formed a
stronger visual instruction than the text prohibition, so accessories could reappear as floating
background icons.

## Validation notes

- The focused original-image, try-on and collage fallback suite passes 24 tests.
- The broader render and pixel-trial suite passes 51 tests after excluding its two HTTP modules.
- Those two HTTP modules cannot collect on native Windows because the existing local object store
  imports Unix-only `fcntl`; this is a pre-existing platform limitation unrelated to the diff.
- Ruff passes for all changed Python files, and focused mypy passes for the four changed source
  modules.
