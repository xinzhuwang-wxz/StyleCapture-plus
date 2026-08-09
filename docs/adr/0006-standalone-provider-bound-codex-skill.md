# ADR-0006: Standalone provider-bound Codex skill

Status: Accepted
Date: 2026-07-26
Superseded in part: ADR-0007 intentionally reuses this Skill as the server-side executor for
product `look.virtual_try_on`; its standalone distribution contract remains accepted.

## Context

ADR-0005 requires product Skills to be thin Product API facades: they must not
copy prompts, expose provider model identifiers, or hold provider credentials.
That remains the correct boundary for StyleCapture H5, backend, Worker, Product
API, and product Skills.

This user-requested artifact has a different distribution contract. It must:

- install and run as a reusable Codex skill without a StyleCapture deployment;
- accept one local real-person photo and one or more local outfit boards;
- call the explicitly selected Volcengine Ark understanding and Seedream models;
- never fall back to a local image model or another AIGC provider; and
- preserve face, head scale, body proportions, camera, and framing across a
  same-person multi-outfit batch.

The current Product API owns persisted Looks and RenderArtifacts and expects
authenticated object-backed product state. It does not expose the standalone
two-local-image contract required by this package. Pretending the two entry
points are the same contract would either make the portable artifact dependent
on a deployed product or duplicate Product API semantics incompletely.

## Decision

Accept one narrowly scoped exception to ADR-0005:

1. `skills/doubao-virtual-try-on` is classified as an independently distributed
   Codex artifact, not a StyleCapture Product API facade.
2. Only this artifact may contain its pinned Ark endpoint, provider model IDs,
   generation prompts, audits, and bounded retry policy.
3. It receives the provider key only from the server-side/runtime environment
   variable `ARK_API_KEY` or a hidden interactive prompt. Keys, base64 inputs,
   signed result URLs, and provider authorization headers must not be persisted
   in the package, manifest, audit, or generation-response log.
4. The artifact sends the user-selected source images to Ark over HTTPS. Its
   documentation must disclose this boundary and require that the caller owns
   or is authorized to use the images.
5. It is forbidden for H5, backend, Workers, product tests, or production render
   flows to import or invoke the standalone scripts. Product runtime continues
   to use capability aliases, Product API contracts, and infrastructure
   adapters under ADR-0005.
6. If the standalone local-image workflow becomes a product capability, it must
   first receive a versioned Product API contract and provider adapter; the
   direct-call exception then ends for that product path.
7. Distribution is source plus a deterministic ZIP. Packaging must fail when a
   required file is missing, a symlink is present, or a likely embedded Ark key
   is detected.

This ADR does not supersede ADR-0005. It accepts a reviewable exception for one
named, non-product-runtime artifact.

## Consequences

- The skill can be installed and shared without deploying StyleCapture services.
- The exact API and models requested by the user remain inspectable and stable.
- Multi-look consistency can be implemented inside the portable artifact through
  one canonical identity/body/camera anchor and cross-look audit.
- The package deliberately duplicates some provider orchestration that product
  runtime keeps behind LiteLLM. Reviewers must prevent the exception from
  spreading to additional product Skills.
- Local source photos leave the machine for Ark processing; callers need informed
  consent, provider access, and an appropriate retention/privacy posture.
- Model upgrades are explicit artifact releases rather than silent provider
  substitution.
- A bounded live smoke on the requested Ark models completed in 150.14 seconds.
  That is acceptable for a standalone Codex artifact, but not for replacing the
  current interactive H5/Product API try-on path.

## Alternatives considered

- **Call the existing Product API render workflow.** Rejected for this artifact
  because it requires a deployed service, authenticated persisted Looks, and
  object-backed assets rather than two local image inputs. It remains the
  required path for product runtime.
- **Add a new Product API before packaging the skill.** Rejected for this focused
  PR because it would expand into product authentication, uploads, persistence,
  asynchronous jobs, OpenAPI generation, and Worker integration. That is a
  separate product slice, not a packaging requirement.
- **Use another hosted or local generator as fallback.** Rejected because the
  user explicitly selected Ark and requires failures to remain truthful.
- **Keep the exception undocumented.** Rejected because it would silently violate
  ADR-0005 and invite accidental reuse in product runtime.

## Verification

- Run the skill structure validator from the Codex skill creator.
- Run `pnpm test:doubao-skill` to verify both CLI contracts and package contents
  without a paid provider request.
- Build the archive twice and verify identical SHA-256 digests.
- Scan every committed and archived file for likely Ark credentials.
- Perform a bounded live single-look smoke only with an authorized runtime key;
  retain sanitized manifests/audits outside the repository.
- Architecture review confirms no product module imports
  `skills/doubao-virtual-try-on`.
- Post-merge cleanup confirms the standalone scripts pass direct mypy, ruff,
  unittest, py_compile, and diff checks.
