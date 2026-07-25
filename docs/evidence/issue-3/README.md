# Issue 3 — real mobile journey evidence

Captured on 2026-07-25 at a 390×844 mobile viewport against the Docker `ai-light`
profile. The journey used a real bundled Feed video, a real lasso gesture, the
production HTTP API and queue, LiteLLM capability aliases, hosted visual grounding
and outfit understanding, and the isolated SAM 2.1 Tiny worker. No fixed result or
curated annotation was returned as live AI output.

1. `01-feed-paused.png` — decoded Feed frame paused for selection.
2. `02-lifted-whole-outfit.png` — the selected pixels lift after the lasso settles.
3. `03-save-success.png` — right-swipe directly on the lifted subject confirms save.
4. `04-look-processing.png` — the real Look is visible immediately while processing.
5. `05-look-processing-detail.png` — source frame and pending component remain honest.
6. `06-look-ready-detail.png` — hosted analysis and the real segmented Item are ready.
7. `07-liking-reason.png` — the optional reason is saved as a preference signal.
8. `08-decomposed-item-wardrobe.png` — the extracted garment appears in “单品”.
9. `09-returned-to-source-time.png` — detail returns to the source Feed at 2.3 seconds.
10. `10-look-partial-failure.png` — a stopped gateway preserves the Look and exposes retry.
11. `11-look-retry-processing.png` — an incomplete retry remains visibly recoverable.
12. `12-look-retry-ready.png` — a fresh real Feed save reaches `ready` with an Item and
    outfit analysis after the scope-check correction.

Live queue tasks finished `ready` in 56.036 and 55.697 seconds. After inference, the bounded
worker used about 666 MiB of its 2 GiB limit; API, H5, LiteLLM, PostgreSQL and Redis
were healthy. Provider/model selection stayed behind LiteLLM aliases and no credential
or provider identifier entered the public API or browser bundle.

The failure/retry run exposed that requiring every grounding-box corner to sit inside a
hand-drawn lasso rejected legitimate edge-crossing garments. Scoping now uses the
component center: out-of-scope detections remain filtered while the real dress completes.
