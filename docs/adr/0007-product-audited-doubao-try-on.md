# ADR-0007: Product runtime adopts the audited Doubao try-on Skill

- Status: Accepted
- Date: 2026-08-09
- Supersedes: ADR-0006 decision 5 for `look.virtual_try_on` only

## Context

The H5 try-on path previously performed one multimodal image edit, with a hosted FASHN adapter
as a narrower fallback. Real product testing showed unacceptable face-identity drift even when
the user supplied a reference photo. The independently packaged `doubao-virtual-try-on` Skill
already implements a stronger linear workflow: understand identity and outfit, generate, audit
identity/outfit/photorealism, then retry with audit corrections.

The product owner explicitly chose this audited Skill workflow over the previous product render
execution path. The Product API, asynchronous job, RenderArtifact storage, privacy, deletion and
fallback contracts remain useful and must not move into H5 or the Skill.

## Decision

1. `look.virtual_try_on` keeps its existing Product API and Worker boundary, but its configured
   Worker executor invokes the versioned `doubao-virtual-try-on` Skill entry point.
2. The Worker builds a deterministic outfit board from the Look's current real Item images and
   supplies that board plus the selected user/fixed-model photo to the Skill.
3. The Skill receives `ARK_API_KEY` only through the child-process environment. The key, input
   images and signed provider URLs are not written to product traces or logs.
4. A result is stored only when the Skill manifest reports `hard_pass=true`. Audit failure is an
   honest degraded RenderArtifact backed by the real Item collage; the Worker does not fall back
   to the former one-shot image edit or FASHN path when the Skill is configured.
5. The Skill version participates in the render input signature, so upgrading its identity
   contract invalidates older generated-result cache entries.
6. The standalone ZIP remains supported. This product integration is a server-side adapter and
   does not expose provider models, endpoints or credentials through H5 or Product API schemas.

## Consequences

- A try-on can require several paid provider calls and take materially longer, but bad-identity
  candidates are rejected instead of displayed as success.
- The backend image now contains the Skill scripts and the Worker needs an Ark key.
- The old LiteLLM/FASHN code remains as compatibility infrastructure for deployments without the
  configured audited executor, but the standard Compose Worker always configures the Skill and
  therefore never enters that legacy path.
- Operational traces identify the stable Skill workflow and selected attempt without exposing
  concrete model IDs or secrets.

## Verification

- Offline Skill contract tests enforce exact-face geometry language and an identity threshold of
  at least 88.
- Provider adapter tests verify secret transport, hard-pass gating and sanitized trace metadata.
- Render processing tests verify the audited Skill takes precedence over both legacy providers.
- A user-authorized real-image retry remains the required visual acceptance check.
