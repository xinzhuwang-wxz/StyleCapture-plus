# Issue #6 public API, Skill, security, and light-performance QA

**Primary target:** `https://119.45.216.38`  
**Audit window:** 2026-07-26 00:55–01:17 UTC  
**Scope:** public edge, Product API, OpenAPI/docs, public Skill, session/cookie/CORS, upload/media ownership, error handling, provider-data leakage, dependencies, host/container posture, backup/restore, and a 30 Mbps low-concurrency load sample.  
**Overall security risk:** **HIGH — two P1 findings remained unresolved at 01:23 UTC.**  
**Production acceptance verdict at 01:23 UTC:** **BLOCKED** by an unmanaged secondary tunnel and an AI cost guard that existed only in the local worktree and was not yet deployed. TLS/ACME permissions, upload-token log redaction, the main-page security headers, and the resource-unsafe backup were corrected and dynamically re-verified during the audit.

No heavyweight AI workload was run. One public Skill recommendation request exercised the real hosted reasoning path; image generation and try-on were not load-tested.

## Executive summary

| Priority | Count | Result |
| --- | ---: | --- |
| P0 / Critical | 0 | No unauthenticated RCE, injection, cross-user private-media read, or committed production secret was found. |
| P1 / High | 2 unresolved | Unmanaged alternate tunnel; AI cost-abuse guard not deployed. Three additional P1 observations were fixed during the audit. |
| P2 / Medium | 4 | No dependency-aware readiness; mutable CDN/support-container dependencies; same-host media-backup limitations; Skill URL/cookie trust. |
| P3 / Low | 1 | Framework-native 404/CORS errors do not use the documented stable JSON envelope. |

The stable IP ingress itself is healthy: HTTP redirects to HTTPS, the IP certificate is trusted, HTTP/2 and HSTS are present, only ports 22/80/443 are reachable, OpenAPI exposes 38 paths, hashed assets are immutable, missing assets return 404, and the 30 Mbps concurrency-2 sample stayed below 405 ms p95.

## P1 findings

### 1. TLS private keys and ACME account keys became world-readable

**Status:** RESOLVED AND RE-VERIFIED at 01:21 UTC. The tree is now `root:root`, directories `0700`, private files `0600`; `nobody` cannot read the key, and the hardened read-only Caddy container serves HTTPS successfully.

**Severity:** HIGH  
**Category:** OWASP A02 Cryptographic Failures / A05 Security Misconfiguration  
**Location:** `deploy/renew-ip-certificate.sh:21-22`  
**Exploitability:** local authenticated user or compromised host-side service  
**Blast radius:** impersonation of the public endpoint for the current certificate lifetime; ACME account takeover and unauthorized certificate operations.

The renewal cleanup applies `chmod 755` to every directory and `chmod 644` to every file under the Let's Encrypt tree. The deployed host confirmed mode `0644` on both `archive/.../privkey*.pem` and ACME `private_key.json`. The certificate itself was valid, but key confidentiality was not.

Secure remediation in Bash:

```bash
# BAD: exposes every private key and ACME account credential to local users.
find "${certificate_root}" -type d -exec chmod 755 {} +
find "${certificate_root}" -type f -exec chmod 644 {} +

# GOOD: keep the tree root-only and expose only a read-only mount to the edge.
chown -R root:root "${certificate_root}"
find "${certificate_root}" -type d -exec chmod 700 {} +
find "${certificate_root}" -type f -exec chmod 600 {} +
```

After fixing permissions, rotate/reissue the endpoint certificate and ACME account key, then prove that an unprivileged account cannot read either key while Caddy still starts.

### 2. Quick Tunnel remains an unmanaged public ingress around Caddy

**Severity:** HIGH  
**Category:** OWASP A05 Security Misconfiguration / A08 Software and Data Integrity Failures  
**Location:** deployed container `stylecapture-tunnel` (not represented in production Compose)  
**Exploitability:** remote, unauthenticated  
**Blast radius:** the full H5 and `/v1` API remain reachable through an ingress that bypasses the documented HSTS/certificate/edge boundary.

The stable IP was fixed, but the earlier Quick Tunnel stayed public. Its HTTP URL returned `200` instead of redirecting, and its container used `cloudflare/cloudflared:latest`, a writable root filesystem, no `no-new-privileges`, no capability drop, no CPU/memory limit, and unbounded `json-file` logs.

Secure remediation in Compose YAML if a tunnel is intentionally retained:

```yaml
services:
  tunnel:
    image: cloudflare/cloudflared@sha256:<reviewed-digest>
    read_only: true
    user: "65532:65532"
    security_opt: ["no-new-privileges:true"]
    cap_drop: ["ALL"]
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}
    deploy:
      resources:
        limits: {cpus: "0.20", memory: 128M}
```

The preferred Issue #6 remediation is to stop and remove the temporary tunnel after the stable IP acceptance run.

### 3. Full local media backup crossed the host disk guard and had no failure cleanup/retention

**Status:** RESOLVED FOR THE LOCAL GUARD at 01:21 UTC. The incomplete 3.39 GB archive was stopped and precisely removed, free space returned to 21 GB, and the replacement defaults to a 1.59 MB PostgreSQL dump plus a 2.25 MB media manifest. Both artifacts are `0600`, checksums pass, an isolated restore produced 12 public tables, and cleanup removed the temporary database. Off-host encrypted media retention remains P2.

**Severity:** HIGH  
**Category:** OWASP A04 Insecure Design / A09 Security Logging and Monitoring Failures  
**Location:** `deploy/backup-state.sh:10-43`  
**Exploitability:** operational or scheduled execution; a repeated or interrupted backup is sufficient  
**Blast radius:** root filesystem exhaustion, database/API outage, and loss of the recovery path it was intended to create.

The first upload-volume backup grew past 3.39 GB while still running. Free root-disk space fell from 21 GB to 18 GB, crossing the repository's 20 GB hard floor. The script had no source-size/free-space preflight, failure trap to remove an incomplete directory, retention policy, or off-host target. The supervising agent stopped it and removed the incomplete directory.

Secure remediation in Bash:

```bash
cleanup_incomplete() {
  if [[ ! -f "${backup_directory}/SHA256SUMS" ]]; then
    rm -rf -- "${backup_directory}"
  fi
}
trap cleanup_incomplete EXIT

available_kib="$(df --output=avail -k "${backup_root}" | tail -n 1)"
required_kib="$((estimated_backup_kib * 2 + 20 * 1024 * 1024))"
if (( available_kib < required_kib )); then
  echo "insufficient backup headroom" >&2
  exit 1
fi
```

For this single host, retain a small verified PostgreSQL dump locally and send encrypted media backups to a separate failure domain. Do not repeatedly clone the multi-gigabyte media volume onto the same root disk.

### 4. Public hosted-AI cost guard was not deployed at audit time

**Severity:** HIGH  
**Category:** OWASP A04 Insecure Design / A05 Security Misconfiguration  
**Location:** costly routes such as `services/backend/src/stylecapture_backend/features/outfit/interfaces/http.py:256-292`; deployment check 01:17 UTC  
**Exploitability:** remote, unauthenticated attacker can create anonymous signed sessions  
**Blast radius:** hosted-model charges, worker/queue saturation, and availability loss.

The public API allowed an anonymous visitor to create a session and invoke outfit planning, capture/retry, pixel generation, and render workflows. At audit time the deployed API did not contain `stylecapture_backend.platform.cost_guard`, while the local worktree contained an untracked Redis guard under concurrent implementation. A source-only fix is not production evidence.

The proposed Python structure is appropriate only after deployment and bounded live verification:

```python
lease = await cost_guard.acquire(
    client_key=trusted_client_key(request),
    actor_key=verified_session_user,
    capability=capability,
)
if not lease.allowed:
    return error_response(
        status_code=429,
        code="ai_quota_exceeded",
        headers={"Retry-After": str(max(1, lease.retry_after_seconds))},
    )
```

Acceptance must prove per-session, per-client, concurrency, and global limits; atomic Redis behavior; fail-closed `503`; trustworthy proxy address derivation; `Retry-After`; and bounded recovery after the window.

## P2 findings

### 5. `/healthz` is a liveness constant and `/readyz` is the SPA

**Severity:** MEDIUM  
**Category:** OWASP A05 Security Misconfiguration / A09 Logging and Monitoring Failures  
**Location:** `services/backend/src/stylecapture_backend/main.py:565-567`, `apps/h5/nginx.conf:18-23,94-95`  
**Exploitability:** operational failure rather than direct attacker input  
**Blast radius:** false-positive health during PostgreSQL, Redis, queue, or provider-path failures; traffic may remain routed to an unusable instance.

`GET /readyz` returned `200 text/html` containing the SPA. `/healthz` returned the constant `{"status":"ok"}` and does not probe dependencies.

Secure remediation in Python:

```python
@app.get("/readyz")
async def readyz() -> Response:
    checks = await asyncio.gather(
        database.ping(), redis.ping(), queue.ping(), return_exceptions=True
    )
    if not all(result is True for result in checks):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return JSONResponse(content={"status": "ready"})
```

Keep provider checks bounded and non-billable; do not perform model inference in readiness.

### 6. Swagger UI depended on resources blocked by the production CSP

**Status:** RESOLVED at the edge for current Swagger resources; the main page and docs now receive CSP, `X-Frame-Options: DENY`, and `Permissions-Policy`. Self-hosting an exact Swagger asset version remains preferable to the mutable `swagger-ui-dist@5` CDN dependency.

**Severity:** MEDIUM  
**Category:** OWASP A05 Security Misconfiguration  
**Location:** `apps/h5/nginx.conf:6,32-44`  
**Exploitability:** public API consumer  
**Blast radius:** `/docs` and `/redoc` render without their scripts/styles, impairing public contract usability.

Initially `/docs` referenced `cdn.jsdelivr.net` while its CSP permitted scripts and styles only from `'self'`. The edge policy was corrected during the audit. The raw `/openapi.json` contract works and exposes 38 paths.

Preferred remediation: self-host pinned Swagger assets under a versioned local path and keep `script-src 'self'`. Broadening CSP to arbitrary CDNs is not recommended.

### 7. Operational helper images are mutable tags

**Severity:** MEDIUM  
**Category:** OWASP A08 Software and Data Integrity Failures  
**Location:** `deploy/renew-ip-certificate.sh:27-36`, `deploy/backup-state.sh:31-35`  
**Exploitability:** registry/tag compromise or unexpected upstream release  
**Blast radius:** the Certbot container receives host networking and write access to certificate credentials; the backup helper receives write access to recovery artifacts.

Pin `certbot/certbot` and `alpine` by reviewed digest. The production Compose services already demonstrate this pattern for Caddy.

### 8. Local backup alone is not a disaster-recovery boundary

**Severity:** MEDIUM  
**Category:** OWASP A04 Insecure Design / A09 Logging and Monitoring Failures  
**Location:** `deploy/backup-state.sh`, `deploy/README.md:42-54`  
**Exploitability:** host/disk failure, compromise, or operator error  
**Blast radius:** simultaneous loss of production and backup; private media exposure if copied without encryption.

The PostgreSQL volume is persistent and a schema-only `pg_dump` smoke succeeded, but the initial audit found no completed dump or restore evidence. A later local backup implementation was still being revised. Require checksums, restrictive permissions, an actual temporary-database restore, encrypted off-host copy, retention, and deletion testing.

## P3 finding

### 9. Edge/framework errors do not consistently follow the stable API envelope

**Severity:** LOW  
**Category:** OWASP A04 Insecure Design / A09 Logging and Monitoring Failures  
**Location:** no Starlette `HTTPException` normalization handler after `services/backend/src/stylecapture_backend/main.py:538-549`  
**Exploitability:** remote, unauthenticated  
**Blast radius:** clients receive inconsistent recovery metadata; security monitoring must parse JSON, text, and HTML forms.

Unknown `/v1` routes returned `{"detail":"Not Found"}`. Rejected CORS preflights returned plain text. Earlier proxy rate-limit responses returned HTML and lacked `Retry-After`.

Secure remediation in Python:

```python
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    return _error_response(
        request,
        status_code=error.status_code,
        code="route_not_found" if error.status_code == 404 else "http_error",
        message="The requested API route does not exist"
        if error.status_code == 404 else "The request could not be completed",
        headers=error.headers,
    )
```

## Verified controls

- **Transport:** primary HTTP returns `308`; HTTPS uses HTTP/2, HSTS `max-age=31536000`, and a trusted short-lived certificate whose SAN is IP `119.45.216.38`.
- **Public surface:** host scan found only `22`, `80`, and `443` reachable; PostgreSQL, Redis, LiteLLM, API, H5, and Caddy admin ports were not public.
- **Session:** `HttpOnly; Secure; SameSite=Strict`; host-only cookie; tampering and absence return `401`; API responses are `private, no-store` and vary on `Cookie`.
- **CORS/CSRF:** hostile-origin preflight returned `400` without `Access-Control-Allow-Origin`. State-changing endpoints consume JSON or custom headers, and the session cookie is Strict.
- **Authorization:** private item media was owner-readable, anonymous access returned `401`, and a second signed session received `404`. Cross-session upload deletion likewise returned `404`.
- **Upload validation:** 20 MiB request and streaming limits, allowlisted MIME, signature/decoder validation, pixel limit, size/hash binding, HMAC-SHA256 token, expiry, single-claim behavior, ownership, and path containment were present. A 20 MiB + 1 request returned `413`; MIME mismatch returned `400`.
- **Injection/XSS:** SQLAlchemy expressions are used for persistence; no user-built SQL, shell command concatenation, `eval`, `os.system`, `shell=True`, React `dangerouslySetInnerHTML`, or unsafe HTML sink was found in the reviewed paths.
- **SSRF:** provider image downloads require public HTTPS, reject credentials/localhost/non-global literal IPs, resolve DNS and reject any non-global result, restrict content type, and bound streamed bytes (`features/render/infrastructure/providers.py:378-447`).
- **Provider/privacy leakage:** public API, recursive response scans, JS/CSS bundles, and recent service logs contained no provider API keys, gateway endpoints, private keys, upload tokens, session cookies, raw prompts, or concrete provider configuration. Product-visible `save_token` and `model_version` fields were expected contracts, not secrets.
- **Secrets:** tracked scans found only documented placeholders and test sentinels. Local `.env` is ignored/untracked. Runtime secret-presence checks found distinct, non-placeholder values without reading or printing them. The `.env` mode was initially `0644` and was corrected to `0600` during the audit.
- **Dependencies:** production npm audit against the official registry reported 0 vulnerabilities across 16 production dependencies. `uv export --frozen --all-packages --no-dev --no-hashes | pip-audit --no-deps` reported no known vulnerabilities across the pinned export; the editable workspace package was skipped because it has no published-version lookup. Container-image CVE scanning was not completed.
- **Integrity:** GitHub Actions used commit-SHA-pinned actions. Core Compose images and service hardening were present; the operational helper/tunnel exceptions are findings above.
- **Static delivery:** current hash assets returned immutable one-year cache headers; missing hash assets returned 404; index returned `no-cache`; Feed media returned cache headers and supported byte ranges.
- **Skill:** `skills/scene-outfit-matching` tests passed 4/4. A live request for `周五面试` / `简洁正式` returned four real plans and a completed three-step trace in 26.0 seconds without provider-key leakage.
- **Performance/resources:** see `metrics.json`. Under a 30 Mbps client cap and concurrency 2, p95 was 185 ms for health, 396 ms for JS, and 405 ms for the first video. Post-load RAM was 1.8/7.4 GiB, swap 12 KiB, and app containers stayed within limits.

## OWASP Top 10 disposition

| Category | Disposition |
| --- | --- |
| A01 Broken Access Control | Pass for reviewed upload/item/media routes; cross-session tests denied access. |
| A02 Cryptographic Failures | **Fail:** TLS and ACME private-key filesystem modes were `0644`. Session/upload HMAC design passed. |
| A03 Injection | Pass for reviewed SQL, command, rendering, and browser sinks. |
| A04 Insecure Design | **Fail:** undeployed cost guard and resource-unsafe backup design. |
| A05 Security Misconfiguration | **Fail:** unmanaged alternate tunnel, missing readiness, and broken docs CSP. Primary IP TLS and headers passed. |
| A06 Vulnerable Components | Application audits passed; container-image audit is an evidence gap. |
| A07 Identification and Authentication Failures | Pass for the signed anonymous-session model and secure cookie contract; paid capability abuse remains A04. |
| A08 Software and Data Integrity Failures | **Partial:** CI/core images pinned; Certbot, Alpine backup helper, and tunnel tags mutable. |
| A09 Security Logging and Monitoring Failures | **Partial:** request IDs/no-store/log redaction passed; readiness, backup lifecycle, and tunnel log bounds failed. |
| A10 Server-Side Request Forgery | Pass for reviewed provider download adapter. |

## Exact acceptance commands

Run after all P1 fixes are deployed:

```bash
base=https://119.45.216.38

# TLS, redirect, headers, liveness/readiness, and OpenAPI.
curl --fail --silent --show-error --head http://119.45.216.38/healthz
curl --fail --silent --show-error --http2 --dump-header - --output /dev/null "$base/healthz"
curl --fail --silent --show-error "$base/readyz" | jq -e '.status == "ready"'
curl --fail --silent --show-error "$base/openapi.json" \
  | jq -e '.openapi == "3.1.0" and (.paths | length) == 38'
echo | openssl s_client -connect 119.45.216.38:443 \
  -servername 119.45.216.38 -verify_return_error 2>/dev/null \
  | openssl x509 -noout -dates -ext subjectAltName

# Cookie and hostile CORS origin.
curl --silent --show-error --request POST --dump-header - --output /dev/null \
  "$base/v1/session" | sed -E 's/(stylecapture_session=)[^;]+/\1<redacted>/'
curl --silent --show-error --request OPTIONS --dump-header - --output /dev/null \
  -H 'Origin: https://evil.example' \
  -H 'Access-Control-Request-Method: POST' \
  "$base/v1/outfit-plans"

# Static cache correctness and Feed byte ranges.
curl --fail --silent --show-error --head "$base/assets/index-Dzek9Hnt.js"
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  "$base/assets/definitely-missing-audit.js")" = 404
test "$(curl --silent -H 'Range: bytes=0-262143' --output /dev/null \
  --write-out '%{http_code}' "$base/feed/media/pexels-9512048.mp4")" = 206

# Host secret/key modes. These checks must fail closed for an unprivileged user.
ssh stylecapture-prod 'stat -c "%a %U:%G %n" \
  /srv/stylecapture/shared/.env \
  /srv/stylecapture/shared/letsencrypt/archive/119.45.216.38/privkey*.pem'
ssh stylecapture-prod 'sudo -u nobody test ! -r \
  /srv/stylecapture/shared/letsencrypt/live/119.45.216.38/privkey.pem'

# Backup integrity and actual isolated restore.
ssh stylecapture-prod 'sudo STYLECAPTURE_REPOSITORY_ROOT=/srv/stylecapture/app \
  /srv/stylecapture/app/deploy/backup-state.sh'
ssh stylecapture-prod 'cd /srv/stylecapture/backups/latest && sha256sum -c SHA256SUMS'
ssh stylecapture-prod 'sudo STYLECAPTURE_REPOSITORY_ROOT=/srv/stylecapture/app \
  /srv/stylecapture/app/deploy/verify-database-backup.sh'
ssh stylecapture-prod 'df -BG /; find /srv/stylecapture/backups/latest \
  -maxdepth 1 -type f -printf "%m %U:%G %s %f\\n"'

# Cost guard deployment and focused tests.
ssh stylecapture-prod 'docker exec stylecapture-api-1 python -c \
  "from stylecapture_backend.platform.cost_guard import costly_capability; \
  assert costly_capability(\"POST\", \"/v1/outfit-plans\") == \"reasoning\""'
uv run pytest services/backend/tests/api/test_cost_guard.py -q

# Remove the obsolete alternate ingress.
ssh stylecapture-prod 'test -z "$(docker ps -q --filter name=stylecapture-tunnel)"'
```

## Reproduction notes

- Public probes used `curl --noproxy '*'` to avoid local proxy artifacts.
- Performance probes used `--limit-rate 3750k` (30 Mbps) and at most two concurrent clients.
- Host checks used the `stylecapture-prod` SSH alias and did not print secret values.
- The initial Quick Tunnel measurements were materially slower than the stable IP: health concurrency-2 p95 7.58 s, JS p95 3.67 s, and first-video p95 5.41 s. Those measurements diagnose the disposable tunnel, not the current primary ingress.
- The audit observed concurrent remediation. Items described as corrected during the window still require the exact final acceptance run on the deployed commit before Issue #6 can close.
