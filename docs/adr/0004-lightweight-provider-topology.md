# ADR-0004: Lightweight-first provider topology

- Status: Accepted
- Date: 2026-07-25

## Context

StyleCapture must preserve a product-quality Feed, garment understanding, similarity,
try-on, and pixel-cover experience without making a GPU server a deployment
prerequisite. The current design names several capable but operationally expensive
self-hosted pipelines: Grounded-SAM2, FashionSigLIP, FastFit, and FASHN VTON. Running
all of them together would make a 24–48 GB GPU the dominant deployment constraint even
though most product intelligence can be served by existing provider APIs.

The user's Feed action is already asynchronous: the client can render the lasso,
lifted subject, and swipe confirmation from the captured frame without waiting for
server inference. This makes model latency a background processing concern rather
than a gesture-path requirement.

Current upstream evidence also supports a smaller topology:

- SAM 2.1 tiny has 38.9M parameters; the quality gap to the 224.4M large checkpoint is
  modest enough to benchmark rather than assume a large checkpoint is required. A
  real project frame benchmark produced a clean 0.974 coat mask at 0.609 seconds warm
  CPU inference with two threads.
- MobileSAM is a 9.66M-parameter promptable segmenter with ONNX export and demonstrated
  CPU operation, so it is a credible fallback for still-frame mask refinement.
- Volcengine exposes visual grounding and multimodal image/text embeddings as hosted
  capabilities.
- FASHN exposes a hosted `tryon-v1.6` endpoint designed for real-time, cost-sensitive
  integrations, while `tryon-max` remains an optional quality tier.
- Seedream supports reference-image editing, so pixel-cover generation need not load a
  local diffusion model.

## Decision

1. The default deployment is **CPU core + hosted intelligence**, not a GPU host.
   The current 4 vCPU / 8 GiB server may run Nginx/H5, FastAPI, PostgreSQL/pgvector,
   Redis/Celery, LiteLLM, and bounded media workers. Feed media and generated artifacts
   are delivered from COS/CDN rather than the server's 5 Mbps link.
2. The synchronous Feed path is model-free. The browser performs frame capture,
   lasso rendering, approximate lifted-subject compositing, and swipe confirmation.
   The API persists the save intent before any AI work begins.
3. `promptable_segmentation` is a provider contract:
   - default `ai-light` demo adapter: SAM 2.1 Hiera Tiny, one still frame at a time
     in the isolated media worker under the `ai-light` profile; it runs on a
     two-thread CPU and needs a 2 GiB worker memory limit;
   - the durable coarse lasso is always retained as the failure fallback and is the
     explicit model-free `core` development mode;
   - MobileSAM/ONNX remains a smaller candidate if later deployment measurements show
   that SAM 2.1 Tiny's roughly 1.25 GiB process peak is unacceptable; larger
   checkpoints and video propagation are not default runtime dependencies.
   Linux installs resolve `torch` and `torchvision` exclusively from PyTorch's
   official CPU wheel index. Pulling CUDA/NVIDIA runtime packages into `ai-light` is
   a deployment regression and a merge blocker.
4. Whole-Look component discovery does not self-host Grounding DINO by default.
   `visual_grounding` routes to Doubao/Ark through the model boundary and returns
   structured garment regions; the promptable segmenter refines those regions.
   Grounded-SAM2 remains an optional benchmark or hosted-provider adapter.
5. `multimodal_embedding` initially routes to hosted
   `doubao-embedding-vision` and combines its vector with deterministic category,
   color, pHash, ownership, and source features. FashionSigLIP remains an optional
   fashion-specific quality comparator or batch provider, not a required resident
   model.
6. Garment tagging and Look analysis use the hosted
   `vision_understanding` alias (`doubao-seed-2-0-lite-260428`). Outfit explanation
   and aesthetic reranking use the hosted `reasoning` alias. Hard constraints,
   state transitions, and purchase logic remain deterministic application code.
7. The default try-on provider is hosted FASHN `tryon-v1.6` in performance or balanced
   mode. `tryon-max` is an opt-in quality tier. Local FASHN VTON and FastFit are
   optional `ai-heavy` adapters only.
8. Pixel Look covers use the existing StyleCapture pixel provider contract routed to
   hosted Seedream reference-image editing. No local diffusion model is required.
9. Provider selection is evidence-gated rather than name-gated:
   - segmentation candidates are compared on the fixed difficult Feed subset for
     garment boundary retention and usable cutouts;
   - embedding candidates are compared on fixed same-item, similar-item, and
     different-item retrieval judgments;
   - try-on candidates are compared on garment fidelity, identity/body preservation,
     latency, and failure rate;
   - a heavier provider is enabled only when the lighter candidate fails the agreed
     product acceptance threshold on real project inputs.
10. All choices remain behind versioned application ports. Provider/model names,
    credentials, payloads, polling, and transport never enter the domain, public API,
    or browser bundle.

## Consequences

- A GPU server is not part of the default deployment budget.
- The existing 4 vCPU / 8 GiB server is viable for a judging deployment when media is
  offloaded to COS/CDN and local media/segmentation concurrency is one.
- The first save interaction remains smooth even when hosted inference takes seconds.
- External APIs introduce network, quota, privacy, and regional-availability risks.
  Jobs therefore retain processing/partial/retry states, bounded retries, provider
  trace metadata, and honest collage fallback.
- New user photos may leave the deployment boundary for configured providers. Product
  consent, retention disclosure, deletion, and server-side credential controls are
  required before public use.
- FashionSigLIP, Grounded-SAM2, FastFit, and local FASHN are preserved as replaceable
  quality options without forcing their weights or CUDA stack into the core image.

## Alternatives considered

- **Self-host every selected open-source model on one 48 GB GPU.** Rejected as the
  default because it optimizes for model ownership rather than the product's measured
  needs and creates unnecessary cost and operational coupling.
- **Use only generic VLM text tags and remove image similarity vectors.** Rejected
  because subtle visual similarity benefits from multimodal retrieval; the hosted
  embedding plus deterministic features is still lightweight.
- **Wait for segmentation before showing the lifted subject.** Rejected because it
  would couple Feed feel to model latency and provider availability.
- **Use browser-only segmentation for the source of truth.** Rejected because mobile
  device variability is too high. Browser compositing is visual feedback; durable
  masks are produced asynchronously behind the provider contract.

## Verification

- Run the fixed Feed regression subset through MobileSAM and hosted SAM 2.1
  tiny/small before locking the deployment adapter; record latency, peak memory,
  failure rate, and visual acceptance.
- Compare hosted multimodal embedding against FashionSigLIP on fixed retrieval
  judgments before removing the optional FashionSigLIP profile.
- Complete at least one uncached Doubao grounding/tagging/embedding request, one
  FASHN try-on, and one Seedream pixel-cover request with trace metadata and no secret
  leakage.
- On the 4 vCPU / 8 GiB target, run the complete mobile journey while recording
  container memory, CPU, queue depth, API latency, and COS/CDN media behavior.

## References

- [Meta SAM 2 model table](https://github.com/facebookresearch/sam2)
- [MobileSAM official repository](https://github.com/ChaoningZhang/MobileSAM)
- [Grounded-SAM2 official repository and hosted grounding options](https://github.com/IDEA-Research/Grounded-SAM-2)
- [Volcengine visual grounding](https://www.volcengine.com/docs/82379/1616136?lang=en)
- [Volcengine multimodal embedding](https://www.volcengine.com/docs/85637/2477596?lang=zh)
- [FASHN Try-On v1.6](https://docs.fashn.ai/api-reference/tryon-v1-6)
- [FASHN Try-On Max](https://docs.fashn.ai/api-reference/tryon-max)
- [Volcengine Seedream image editing guidance](https://www.volcengine.com/docs/82379/1829186)
