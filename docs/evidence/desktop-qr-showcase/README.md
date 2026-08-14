# Desktop QR showcase evidence

## Result

- Desktop (`2048×1270`): the existing centered phone is unchanged; equal-size website and experience-group QR cards occupy the two presentation rails.
- Mobile (`390×844`): presentation-only QR cards are hidden and the product remains full-width.
- Visual Verdict: **96/100 — pass**.

## Functional evidence

- Website QR decoded from the source asset and the desktop screenshot as `https://119.45.216.38/`.
- Experience-group QR decoded from the source asset and the desktop screenshot as the supplied WeChat group URL.
- The screenshots were captured through the Vite development proxy connected to the public backend, so the wardrobe contains real public data.
- The earlier local `HTTP 500 session_unavailable` screenshot came from Vite static preview, which does not proxy `/v1`; public `/healthz` and `/readyz` remained healthy.

## Automated verification

- H5: 37 test files, 297 tests passed.
- H5 typecheck passed.
- H5 production build passed (549 modules transformed).

Public post-deployment screenshots and smoke results are added after the exact merged `origin/main` commit is deployed.
