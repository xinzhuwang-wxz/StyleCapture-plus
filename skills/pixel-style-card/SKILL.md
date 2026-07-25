---
name: pixel-style-card
description: Turn a user-provided real-person photo or outfit reference into a light, coarse-pixel character card for small-scale creative testing and design exploration. Use for one-off image-to-image pixel-card experiments that preserve the subject, clothing, pose, props, and scene mood while adapting the frame, palette, doodle icons, and sparse floating accents to the source. This is not a production feature or a dependency of any core StyleCapture user journey.
---

# Experimental Pixel Style Card

Create one polished 3:4 pixel-character card from a supplied image. Treat this as a limited creative test utility: use an available image-generation tool, return its result honestly, and do not claim production reliability, automation, or provider integration.

## Boundaries

- Require a user-provided person photo or outfit-reference image; optional user-provided card examples may guide **pixel scale and density only**.
- Do not call or configure a StyleCapture API, Worker, model alias, provider, or environment variable.
- Do not make a generated card a source of truth for an `Item`, `Look`, `RenderArtifact`, recognition result, purchase decision, or Feed behavior.
- Do not bundle, commit, or reproduce user photos, reference images, hidden drafts, keys, or generated results unless the caller separately asks for that artifact handling.

## Build a source brief

Before generating, identify internally:

- the visible identity cues, pose, full outfit construction, footwear, accessories, and meaningful held props;
- the setting, dominant background hues, formality, and emotional tone;
- two outfit accent colors;
- one theme-appropriate frame grammar, one ground treatment, 1–3 source-related doodle icons, and 6–14 small floating accents.

Choose the theme from the clothes and context, not apparent gender. Preserve the source's mood without reconstructing its photographic background literally.

## Lock the character style

- Use a centered, full-body, compact semi-chibi character; keep hair-to-footwear visible whenever the source permits it. For a garment-only input, use a neutral anonymous mannequin-like character and make the garment—not an invented identity—the priority.
- Preserve the source pose, clothing silhouette and color blocking, glasses/jewelry, footwear, and recognizable props. Simplify unreadable prop text rather than inventing new lettering.
- Use deliberately coarse, square pixel clusters: conceptually render low resolution and enlarge with nearest-neighbor scaling. Blocks should read roughly as **6–10 final pixels**, not micro-pixel texture.
- Limit the palette: 2–3 tones for the background, 3–4 tones per clothing plane, and 4–5 tones for face and hair. Use stepped edges, short highlights, sparse dithering, and a thin dark outline.
- Give the face a clear, warm, readable expression. Keep eyes large enough to read at card size, with simple chunky iris/highlight clusters; do not make the face tiny, realistic, or over-painted.
- Avoid grain, hatching, pores, photorealistic materials, 3D shading, blur, painterly rendering, and dense pixel noise.

## Use a lightweight, adaptive background

Build an **icon stage**, not an empty color field and not a miniature detailed scene:

1. Use a calm two-tone base derived from the source background.
2. Add 1–3 small, cute, outline-style pixel doodles based on real source objects or setting cues; place them near edges or behind the lower body.
3. Add 6–14 sparse floaters such as stars, dots, leaves, diamonds, bolts, tiny hearts, or thematic marks.
4. Add one soft oval, floor line, plinth, or shadow under the character.

Keep all background elements lower-contrast and lighter than the character. Do not render a full room, gallery, street, landscape, brick wall, or detailed texture.

Adapt rather than default:

- Formal, dark, sporty, neutral, or museum-like sources use a restrained palette that echoes the source (for example navy/gold, ochre/tan, charcoal/green); do not default to pink, lavender, bows, hearts, rabbits, or flowers.
- A museum/gallery source may use tiny warm-brown line doodles of an elephant, mask, sculpture, or plinth plus sparse gold star dots—never giant statues or a full gallery.
- A beach source may use a shell, wave, sun, or sandal icon; a street/sport source may use a ball, sneaker, or bolt; a forest source may use a leaf, mushroom, or small tree. Use only what relates to the source.

## Card shell

- Use a slim, light, theme-matched double frame with simple stepped corners.
- Let the source background hue lead the field and the outfit colors lead accents.
- Keep decoration airy. Bows, mascots, hearts, flowers, and large corner ornaments are optional and must match the brief; they are never default decoration.
- Do not add unrelated characters, captions, watermarks, logos, or random text.

## Prompt skeleton

```text
Turn the supplied photo into one light 3:4 full-body pixel character card. Preserve [identity cues, pose, outfit construction, clothing colors, footwear, accessories, and meaningful held props]. Simplify the source setting into an airy icon stage rather than rebuilding it realistically.

Theme: [theme]. Two-tone base: [source-derived tones]. Outfit accents: [two colors]. Frame: [slim frame]. Doodle icons: [1–3 source-related simple icons]. Floating accents: [6–14 sparse marks]. Ground: [oval/floor/plinth/shadow]. Keep the decoration lighter and lower-contrast than the character.

Use deliberately coarse cute pixel art: visible 6–10 px square block clusters, clean stepped edges, 2–3 background tones, 3–4 clothing tones, 4–5 face/hair tones, sparse dithering, and thin dark pixel outlines. Give the subject a clear expressive pixel face with readable chunky eyes. Avoid fine detail, grain, hatching, realistic textures, dense scenery, 3D, painterly rendering, blur, empty flat backgrounds, fixed pink/lavender themes, and unrelated decoration. No text or watermark.
```

## Result gate

Deliver the first usable result immediately. Ask for a targeted retry only if a clear failure is visible:

- the pixels are too fine, noisy, realistic, or painterly;
- the person, outfit, pose, footwear, accessory, or key prop is lost;
- the background is empty or becomes a detailed realistic scene;
- doodles do not relate to the photo, overpower the subject, or clash with its formality/palette;
- a fixed sweet/pink/bow motif was imposed without source support.

For a retry, specify the failed constraint directly, for example: “Increase the pixel block size, reduce texture, use [source-related icons] and [palette], and preserve [lost clothing/prop/pose detail].”
