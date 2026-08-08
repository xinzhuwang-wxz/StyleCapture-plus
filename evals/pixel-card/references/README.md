# Pixel character card references

These two source photos are the contributor-approved inputs paired with the bundled positive style anchors:

| Source input | Positive output anchor | Evaluation role |
| --- | --- | --- |
| `source-formal-light.jpg` | `services/backend/src/stylecapture_backend/features/render/assets/pixel-card-references/anchor-formal-light-pixel.png` | Light/formal full-body completion, restrained card spacing, preserved clothing details |
| `source-casual-dark.jpg` | `services/backend/src/stylecapture_backend/features/render/assets/pixel-card-references/anchor-casual-dark-pixel.png` | Casual/dark character proportions, expressive face, coarse pixel treatment |

Runtime sends only the two positive output anchors. It uses them for character style, face proportions, coarse pixels, card spacing, and rug structure; it must not copy their pink/purple palettes or decorations.

Negative examples remain outside the repository. Their failure modes are encoded as assertions and review rules: no fixed pink bow template for formal or masculine outfits, no pure empty background, no photorealistic or over-detailed scene recreation, and no fine-grained pseudo-pixel texture.

The contributor explicitly provided these files for use as StyleCapture-plus GitHub references on 2026-08-08.
