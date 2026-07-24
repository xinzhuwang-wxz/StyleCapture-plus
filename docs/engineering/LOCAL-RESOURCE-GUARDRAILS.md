# Local Resource Guardrails

状态：Active
日期：2026-07-25

The overnight development loop must make progress without keeping the MacBook at sustained full load.

## Default execution profile

- Run the web app, API, PostgreSQL/pgvector, Redis and normal workers through Docker Compose so the same topology can move to Linux later.
- Use Compose profiles: `core` for ordinary development, `ai-light` for genuinely lightweight local inference, and `ai-heavy` only on a measured GPU host.
- Do not run FastFit, FASHN, a large VLM, or concurrent video/model batch processing on the laptop.
- Use at most two normal worker processes and one media/AI job at a time locally.
- Keep the curated Feed corpus outside the runtime inference queue. Manual `curated_seed` annotation must not trigger provider calls.

## Resource checks

Before and during builds, E2E runs, corpus processing, or any task lasting more than a few minutes, inspect:

- system load and top CPU consumers;
- memory pressure and swap growth;
- thermal throttling indicators;
- available disk space;
- Docker container CPU, memory and process counts.

Recheck at least every five minutes while a long local task is active. Reduce parallelism or stop the expensive process when any of these is true:

- macOS reports critical memory pressure or thermal throttling;
- swap grows continuously across two checks;
- free disk falls below 20 GB;
- the same development process sustains more than 80% of total CPU capacity across two checks;
- a container exceeds its documented memory limit or repeatedly restarts.

Recovery order:

1. Stop duplicate watchers and unused development containers.
2. Reduce test, worker, FFmpeg and build concurrency.
3. Run targeted checks sequentially.
4. Move the capability to a hosted provider or defer only its heavy live smoke to Issue #6.

Never hide an unfinished capability behind a mock because a local resource guard fired.

## Docker portability requirements

- Application behavior is configured by environment and capability aliases, not host-specific paths.
- Containers use health checks, bounded logs, explicit volumes, non-root runtime users where practical, and documented CPU/memory limits.
- Media moves through S3-compatible object keys; a local adapter is allowed only behind the same object-store contract.
- Database migrations run explicitly and are reversible; container recreation must not destroy named-volume data.
- CUDA providers live in separate optional images. The core Compose project must build and run without CUDA.
- The deployment Issue verifies the same Compose contracts on a clean Ubuntu host.

## Visual and user evidence

Every user-visible milestone must include:

- a real mobile browser run through the affected journey;
- screenshots at the approved viewport for the changed initial, interaction, processing, success, failure and recovery states;
- a short record of the exact input, API/trace ID and observed result;
- a visual verdict and fixes for every P0/P1 issue before merge.

DOM assertions or unit tests alone do not count as user-interface acceptance.
