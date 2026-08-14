# Desktop QR showcase

## Goal

Use the desktop whitespace around the existing phone simulator to provide two obvious roadshow entry points while leaving the mobile product untouched.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Desktop presentation shell | `PhoneFrame.tsx`, `.pixel-stage`, `.pixel-frame` | Adapted reuse | This is already the single responsive boundary for browser demos and mobile passthrough. | Repository `main@3c0fc67`, project license |
| Website QR | User-supplied `25881786681643_.pic.jpg` | Direct reuse with CSS crop | The encoded destination is already approved; CSS removes only the embedded caption. | Product-owner supplied asset, 2026-08-14 |
| Experience group QR | User-supplied `IMG_2481.jpg` | Direct reuse | Existing WeChat group QR must remain byte-faithful for scanning. | Product-owner supplied asset, 2026-08-14 |
| QR generation package | Repository dependencies and hosted generators | Rejected | Static approved codes already exist; generation adds risk and no user value. | Not applicable |

## Decisions

- Render static assets in `PhoneFrame`; do not inject HTML at the proxy layer.
- Keep QR cards hidden below 1180px.
- Use identical component markup and CSS dimensions for both cards.
- Preserve QR pixels; use CSS framing rather than AI image editing.

## Verification

- [x] Red/green component test.
- [x] H5 tests, typecheck, build.
- [x] Desktop and 390×844 screenshots.
- [x] Visual Verdict >= 90.
- [ ] PR, merge, exact-commit deployment, public smoke.

## Progress

- [x] Confirmed `main` and `origin/main` at `3c0fc67` before starting.
- [x] Inspected the existing presentation boundary and rejected duplicate shells.
- [x] Implement and verify locally against the public API.
- [x] Decode both QR assets and both codes from the desktop screenshot.
- [ ] Merge, deploy the exact `origin/main` commit, and repeat the smoke test on the public URL.

## Decision log

- 2026-08-14: Use the existing React presentation boundary with static bundled assets so deployment remains portable and the business UI stays unchanged.
- 2026-08-14: Increase both presentation cards to 348px while preserving equal dimensions and the centered 390×844 phone.
