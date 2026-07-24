# Third-party and reference reuse notes

StyleCapture-plus prefers audited reuse over reimplementing mature capabilities.

## Production-visible reuse in Issue #1

- The default pixel character image was derived from the repository-local `StyleCapture-main` prototype asset and resized for web delivery. It remains a presentation asset; canonical garment data is not reduced to pixel art.
- The React/Vite mobile-shell conventions and Python workspace conventions were adapted from the repository-local Feed prototype. No runtime code imports `_ref`.
- Image validation, asynchronous lifecycle, and manual-field protection patterns were informed by `wardrowbe`, licensed under MIT in `_ref/third-party/wardrowbe/LICENSE`. The current implementation uses its own Capture/Item contracts, Celery runtime, LiteLLM boundary, and persistence schema.

## Deferred projects

Grounded-SAM-2, SAM 2, FashionSigLIP, FASHN VTON, FastFit, and product-taxonomy sources remain isolated under `_ref`. Their code is not part of the Issue #1 production bundle. Any later reuse must preserve the corresponding upstream license, pin the reviewed revision, and stay behind a StyleCapture-owned API boundary.

`_ref` is excluded from Docker build context and production modules. This prevents accidental shipping or deep imports from reference projects.
