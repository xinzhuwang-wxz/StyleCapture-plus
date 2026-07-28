# Issue #46 — Local one-click deployment

## Observable outcome

A clean Docker-capable workstation can start the complete lightweight StyleCapture
stack with `./scripts/local.sh up`, configure a hosted API/subscription behind LiteLLM,
and stop or restart it without losing wardrobe data.

## Reuse audit

| Capability | Candidates inspected | Decision | Reason | Source / license |
| --- | --- | --- | --- | --- |
| Local topology | Existing `docker-compose.yml`; new installer; Kubernetes | Directly reuse Compose with a thin command wrapper | The complete portable topology, health checks and volumes already exist; another deployment system would duplicate it | Repository commit `7ff5c8e7507dec9d3583d8eb01d95d650467b455`; repository-owned code, no separate `LICENSE` file |
| Provider routing | Existing LiteLLM gateway; direct provider SDKs; per-feature keys | Adapt existing LiteLLM environment substitution | Keeps stable capability aliases and server-only credentials while allowing supported provider/model overrides | LiteLLM `v1.90.6`, commit `5113f5d53d1d22c53c0326cdc2e3382c9f907883`, MIT |
| Local secret bootstrap | Manual copy; dotenv dependency; shell + existing `.env.example` | Adapt the existing template with Bash and `openssl`/`/dev/urandom` | Avoids a new dependency and never overwrites an existing environment file | Repository commit `7ff5c8e7507dec9d3583d8eb01d95d650467b455`; macOS/Linux system tools under operating-system distribution terms |
| Package mirror configuration | Existing production Compose overrides; hard-coded new downloader | Adapt the already proven production build arguments for local Compose | Keeps one Dockerfile and makes constrained networks configurable without changing runtime behavior | Repository commit `7ff5c8e7507dec9d3583d8eb01d95d650467b455`; repository-owned code, no separate `LICENSE` file |

## Implementation and verification

- [x] Preserve the verified Doubao/Ark defaults behind environment-driven LiteLLM aliases.
- [x] Add an idempotent local entry point for init, doctor, up, status, logs, restart and down.
- [x] Keep `down` non-destructive and persistent named volumes unchanged.
- [x] Document full-capability Ark and bounded OpenAI-compatible configurations.
- [x] Run shell syntax, unit tests, Compose config, LiteLLM config, build and local readiness checks.
- [x] Complete independent standards/spec review and resolve blocking findings.

## Decisions

- Do not add a second orchestrator. Compose remains the source of runtime truth.
- The local wrapper supplies the distinct default project name `stylecapture-local` so it
  cannot reconcile or stop a same-host production project named `stylecapture`.
- Do not promise provider equivalence. Unsupported image/embedding capabilities fail
  truthfully instead of receiving mock output.
- The one-click wrapper retries only Compose builds at most three times so a transient
  package-registry reset is recoverable, while migration/runtime failures remain immediate
  and truthful instead of triggering redundant rebuilds.

## Surprises & discoveries

- A pre-existing local PostgreSQL volume referenced a lost development migration revision
  (`20260727_0017`) that does not exist in any repository branch or image. The installer
  correctly failed without deleting or rewriting user data. A clean, isolated Compose
  project then completed migrations and startup successfully, proving the repository's
  one-click path while preserving the old volume for manual recovery.
- Fresh Docker builds could intermittently fail against the default npm registry in the
  current network. Reusing the production-configurable Python and npm mirror build arguments
  made the clean build repeatable without adding a downloader or changing runtime semantics.

## Verification evidence

- `bash -n scripts/local.sh`
- `python3 -m unittest tests/test_local_deploy.py` — 3 passed
- `.venv/bin/pytest -q` — 310 passed
- `pnpm typecheck`
- `pnpm test` — 246 H5 tests, 5 scene-outfit Skill tests and 6 Doubao Skill tests passed
- Local and production `docker compose config --quiet`
- Clean `core` Compose build/start with healthy H5, API, PostgreSQL, Redis, LiteLLM and Worker
- Default `stylecapture-local` project isolation, non-destructive restart/reconciliation and cleanup
- `/healthz`, `/readyz`, `/openapi.json` and LiteLLM `/v1/models` smoke checks
- Real hosted-provider request through the stable `reasoning` alias
- Clean Ubuntu full-stack build was not rerun for this change; production Compose rendering
  passes and the local script records its macOS Docker Desktop validation scope explicitly.
