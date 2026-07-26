# Issue #31: Portrait Pixel Character Cards

**Issue:** https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/31  
**Branch:** `fix/issue-31-portrait-pixel-cards`

## Goal

Make person-focused pixel cards consistently render as complete vertical 3:4 cards, rather than accepting a square canvas from a caller and visually compressing or cropping the subject.

## Scope

- Update `photo.pixel_trial` and `look.pixel_cover` prompts and image-generation requests to use a 3:4 portrait canvas (`1536x2048`).
- Make the profile pixel-trial preview reserve a 3:4 portrait area and contain the returned card without distortion.
- Cover the generation contract with focused backend tests.

## Non-goals

- Do not change `item.pixel_presentation`: item presentation remains intentionally square (1:1).
- Do not add a second standalone Skill entry point; the merged product capability remains the source of truth.
- Do not change image providers, model credentials, or storage behavior.

## Reuse audit

- Reuse the existing `PixelTrialProcessor` and `RenderProcessor` image-generator contracts; no provider integration is needed.
- Reuse existing prompt-version and processor test suites to lock the size and prompt contract.
- Reuse the existing profile preview component and its CSS selector; adapt its layout instead of adding a duplicate preview component.
- Keep the existing 3:4 outfit-card layout in the wardrobe UI; correct the upstream output that feeds it.

## Implementation plan

1. Add explicit portrait-ratio language and `1536x2048` requests to the two person-card generation paths; increment their prompt versions.
2. Update focused backend tests to assert the portrait request and ratio constraints.
3. Give the profile trial preview a 3:4 box with `object-fit: contain` so it is a visual guardrail for returned images.
4. Run targeted backend tests and H5 type/build checks, then inspect the diff before opening a focused PR.

## Progress

- [x] Identified that generic `2K` requests and both person-card prompts do not lock an aspect ratio.
- [x] Implement generator, prompt, test, and preview changes.
- [x] Verify focused backend tests (13 passed), backend lint, H5 type checking, and a 390x844 local-browser preview.
- [ ] Open a focused PR.
