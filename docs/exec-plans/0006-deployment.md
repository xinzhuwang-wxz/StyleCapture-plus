# Issue #6 — judging deployment and final acceptance

## User outcome

A judge opens a browser-trusted HTTPS URL on a phone, scrolls the real Feed, circles and
saves an item or Look, uploads or photographs a garment, receives real asynchronous
understanding, uses the seeded and personal wardrobe to generate outfit plans, renders a
real collage/pixel cover/Seedream try-on, and can invoke the same workflow through the
packaged Skill. Processing, failure and recovery states remain honest and traceable.

## Deployment shape

- Tencent Cloud SA9, Ubuntu 24.04, 4 vCPU / 8 GiB / 5 Mbps.
- Caddy official image for automatic HTTPS at `119-45-216-38.sslip.io`.
- Existing H5/Nginx, FastAPI, PostgreSQL/pgvector, Redis/Celery and LiteLLM containers.
- One `core` worker with concurrency one; hosted Doubao/Seedream providers by default.
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
- [ ] Validate production Compose locally and through CI-quality targeted checks.
- [ ] Deploy the server-only environment and complete stack.
- [ ] Verify trusted HTTPS, camera availability, service health and non-public internal
  ports.
- [ ] Run the real H5 main journey and Skill against the public Product API, saving
  screenshots, trace IDs, provider versions, latency and resource evidence.
- [ ] Test slow/failing provider recovery, session/media privacy, data deletion, backup
  and restart persistence.
- [ ] Run final architecture, security/privacy, license, visual and code reviews; fix all
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

## Surprises and discoveries

- The server disk pressure came from 31.6 GiB of unused Docker images and 14.8 GiB of
  build cache, not active product data. Safe cleanup recovered enough space without
  deleting any volume.
- The checked-in Feed corpus is only about 5.3 MiB and curated backend assets about
  52 MiB. Direct hosting is adequate for the first single-judge smoke; COS/CDN remains
  the measured scale path rather than a blocker to public deployment.
