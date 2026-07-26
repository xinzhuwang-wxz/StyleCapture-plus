# Issue #6 — judging deployment and final acceptance

## User outcome

A judge opens a browser-trusted HTTPS URL on a phone, scrolls the real Feed, circles and
saves an item or Look, uploads or photographs a garment, receives real asynchronous
understanding, uses the seeded and personal wardrobe to generate outfit plans, renders a
real collage/pixel cover/Seedream try-on, and can invoke the same workflow through the
packaged Skill. Processing, failure and recovery states remain honest and traceable.

## Deployment shape

- Tencent Cloud SA9, Ubuntu 24.04, 4 vCPU / 8 GiB / 30 Mbps.
- Caddy official image terminates HTTPS at `119.45.216.38` with a browser-trusted
  Let's Encrypt IP certificate. The earlier `nip.io` / `sslip.io` hostname route was
  rejected after DNS interception made ACME validation unreliable.
- Existing H5/Nginx, FastAPI, PostgreSQL/pgvector, Redis/Celery and LiteLLM containers.
- One `core` worker with bounded concurrency two; hosted Doubao/Seedream providers by
  default.
- Local S3-compatible object-store adapter on the persistent upload volume for the first
  public smoke. Move large media to COS/CDN if measured bandwidth affects judging; no
  Product API or domain contract changes are allowed.

## Progress

- [x] Confirm Issue #6 and competition deliverables require an interactive H5 and a
  Skill/Agent facade over the same Product API.
- [x] Establish key-based SSH alias `stylecapture-prod` without exposing private key
  material.
- [x] Audit the host: Ubuntu 24.04 x86_64, 4 cores, 7.4 GiB RAM, 50 GiB disk, Docker
  29.1.3 and Compose 2.40.3, no active old workloads.
- [x] Reclaim stopped Docker containers, unused images and build cache while retaining
  all prior named volumes and `/home/ubuntu/rel001`; disk usage fell from 84% to 28%.
- [x] Validate production Compose locally and through CI-quality targeted checks.
- [x] Deploy the server-only environment and complete stack.
- [x] Verify trusted HTTPS, camera availability, service health and non-public internal
  ports.
- [x] Run the real H5 main journey and Skill against the public Product API, saving
  screenshots, trace IDs, provider versions, latency and resource evidence.
- [x] Test slow/failing provider recovery, session/media privacy, data deletion, backup
  and restart persistence.
- [x] Run final architecture, security/privacy, license, visual and code reviews; fix all
  P0/P1 findings before merge and Issue closure.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Public HTTPS edge | Existing H5 Nginx; hand-written ACME; Caddy official image | Adapt Caddy as a thin edge in front of existing H5 | Browser-trusted HTTPS is required for mobile camera use; Caddy avoids custom certificate automation | `caddy:2.10.2-alpine`, image revision `272e3f8`, Apache-2.0 |
| Application topology | Existing `docker-compose.yml`; old `/home/ubuntu/rel001/infra` | Extend the current Compose with a production override | Preserves tested health checks, limits, volumes and service contracts without copying the unrelated old infra stack | This repository |
| Model routing | Direct Ark calls; existing LiteLLM gateway | Directly reuse LiteLLM aliases | H5, Skill and domain code remain provider-neutral and keys stay server-only | LiteLLM in current backend image, MIT |
| Recommendation Skill | New Skill server; current `scene-outfit-matching` | Directly reuse current thin Skill facade | It already calls the generated Product API and trace contracts; a second implementation would drift | This repository |
| Image/try-on generation | Local GPU stack; FASHN; current Seedream image edit | Reuse Seedream through `image_generation`, keep FASHN optional | Full multi-reference result without GPU capacity or a second public contract | Volcengine Ark API; current adapter |

## Decision log

- Use the existing 4C8G host as the final default deployment. A GPU host is rejected
  unless measured real-provider quality or throughput fails.
- Keep curated seed assets explicitly enabled in production for the judging cold start;
  provenance remains `curated_seed` and is never represented as live AI output.
- Preserve old Docker volumes until the new product has passed persistence and backup
  tests. Only rebuildable stopped containers, images and build cache were removed.
- Keep the portable CPU deployment's garment image contract truthful: it guarantees a
  browser-safe normalized garment crop and a real generated pixel presentation. Full
  alpha-matte SAM2 extraction stays in the optional `ai-light` profile and is not a
  judging-path dependency on this CPU host.
- Remove the temporary Cloudflare tunnel after the direct HTTPS edge passed. A second
  public path would bypass the hardened Caddy policy and make the submitted URL
  ambiguous.

## Surprises and discoveries

- The server disk pressure came from 31.6 GiB of unused Docker images and 14.8 GiB of
  build cache, not active product data. Safe cleanup recovered enough space without
  deleting any volume.
- The checked-in Feed corpus is only about 5.3 MiB and curated backend assets about
  52 MiB. Direct hosting is adequate for the first single-judge smoke; COS/CDN remains
  the measured scale path rather than a blocker to public deployment.
- GitHub HTTPS clone and the default overseas PyPI artifact downloads were extremely
  slow from the host. Deployment now transfers the exact local commit over SSH and uses
  Tencent Cloud's internal PyPI mirror plus npmmirror only through optional Docker build
  arguments; normal Dockerfile defaults still use the official registries.
- `uv.lock` stores immutable `files.pythonhosted.org` artifact URLs, so changing only
  `UV_DEFAULT_INDEX` did not affect locked downloads. The production build optionally
  rewrites those copied in-image URLs to Tencent's path-compatible HTTPS mirror while
  retaining every locked hash; the tracked lockfile remains byte-identical.
- Public headless testing revealed that browser background throttling paused wardrobe
  query polling while Feed processing continued. Enabling background polling for the
  Look list/detail made the right-swipe save recover from `processing` to the completed
  Look without forcing a refresh.
- A final upload rerun hit one transient wardrobe-list read failure after navigation.
  The product correctly rendered a non-destructive retry state; the E2E now exercises
  that recovery instead of treating a temporary read failure as an empty wardrobe.
- The canonical transparent PNG produced by the upload pipeline was 1.81 MiB. The API
  now preserves that source while serving a browser-optimized 274 KiB WebP derivative;
  the item detail uses native image streaming over HTTP/2 instead of buffering the
  entire object in browser JavaScript.

## Final verification evidence

- Backend: `295 passed`; Ruff and mypy clean.
- H5: `87 passed`; TypeScript clean. Skill package: `4 passed`.
- Public mobile, 390x844: five top-level tabs, Feed pause/resume and lasso guidance,
  cancel/save gestures, whole-Look ingestion, real upload and persistence, pixel Try,
  Chinese AI recommendation, progressive outfit delivery, Look save, personal try-on,
  API-level source deletion and failure recovery.
- Production: `/readyz` verifies PostgreSQL, Redis and LiteLLM; only 22/80/443 are
  exposed; HSTS/CSP and upload-token log filtering are active; Redis cost/concurrency
  guard, database restore, certificate renewal timer and 30 Mbps load checks passed.
- Judge instructions: `docs/judging/DEMO-GUIDE.md`.
