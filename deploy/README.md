# StyleCapture judging deployment

The judging environment runs the complete interactive H5 and Product API on one small
Ubuntu host. Caddy terminates HTTPS, the existing H5 Nginx container serves the React
application and proxies Product API calls, and the API/worker use PostgreSQL, Redis and
LiteLLM on the private Compose network. Only ports 80 and 443 are public.

The default deployment uses the `core` worker and hosted intelligence. It never loads a
GPU model. Seedream handles pixel generation and multi-reference try-on through the
`image_generation` LiteLLM alias; the Doubao Lite aliases handle garment understanding,
grounding, outfit analysis and recommendation. The optional `ai-light` profile replaces
the coarse selection fallback with CPU SAM2 Tiny and must be measured before activation.

## Server preparation

Ubuntu 22.04 or 24.04 with Docker Engine and Compose v2 is supported. Copy
`deploy/production.env.example` to a server-only `.env`, generate unique secrets, and
set `ARK_API_KEY`. Never commit or expose that file.

The example also enables Tencent Cloud's HTTPS PyPI mirror and the public npmmirror
registry as build-only inputs. Because `uv.lock` records immutable artifact URLs, the
optional `UV_LOCK_MIRROR_BASE` rewrites only the copied lockfile inside the image build;
package hashes remain enforced and the repository lockfile is untouched. The
Dockerfiles retain the official package registries as their defaults, so local and
non-Tencent builds are unchanged.

```bash
docker compose \
  --env-file .env \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  --profile core \
  up --build -d
```

The current judging URL is `https://119-45-216-38.sslip.io`. `sslip.io` resolves the
hostname to the public IP, allowing Caddy to obtain a normal browser-trusted certificate
without inventing a custom TLS implementation. A competition-owned domain can replace
the host without changing any application contract.

## Health and operations

```bash
curl --fail https://119-45-216-38.sslip.io/healthz
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml ps
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml logs --tail=200
```

Application state is held in named PostgreSQL, Redis, upload and Caddy volumes. Build
cache and stopped images may be removed without deleting those volumes. Database and
private upload backups must be taken before volume deletion or host replacement.

## Skill delivery

`skills/scene-outfit-matching` is the public Skill facade for the recommendation
workflow. It calls the same `/v1/outfit-plans` and trace endpoints as the H5 and never
duplicates prompts or provider configuration.

```bash
cd skills/scene-outfit-matching
npm test
STYLECAPTURE_API_URL=https://119-45-216-38.sslip.io \
node scripts/match.js --request '{"scene":"周五面试","style":"简洁正式"}'
```

Internal single-node capabilities remain governed as AI Capabilities rather than being
wrapped in duplicate Skills. Their prompts, schemas, aliases and Promptfoo evaluation
entry points are indexed in `docs/ai/README.md`.
