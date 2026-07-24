# 码上搭：抖音 AI 数字衣橱助手 PRD

状态：Ready for Issues
版本：1.1
日期：2026-07-25

## Problem Statement

用户的服装资产分散在真实衣柜、购物记录、收藏截图和短视频种草内容中。用户既不清楚自己已经拥有什么，也很难判断一件新衣是否适合自己、能否和已有衣服组成完整穿搭。

今天的视觉搜索通常停在“这是什么”或“搜同款”。但用户看到穿搭内容后的真实任务是连续的：

1. 我喜欢的是其中一件，还是整套搭配？
2. 我怎样在不打断刷 Feed 的情况下保存它？
3. 保存后能否拆成可管理、可检索的服装资产？
4. 这件新衣与我已有衣服是否能搭？
5. 某个具体场景下，我现有衣橱能否组成完整方案？
6. 如果缺少单品，能否一次看到需要补齐的内容并完成购买？
7. 推荐结果能否用真实单品与真人效果图展示，而不是只给文字建议？

抖音具备内容种草、商品供给和交易承接能力，但 Feed 中被激发的穿搭兴趣还没有自然沉淀为用户长期可用的数字资产。若识别过程过重、要求用户等待 AI 或连续填写信息，又会破坏 Feed 的核心消费体验。

项目需要解决两个彼此独立但能形成闭环的问题：

- 资产问题：用户不知道自己拥有、收藏或想买哪些衣服。
- 决策问题：用户不知道这些衣服如何搭配，以及缺少什么。

## Solution

码上搭是一套以视觉为入口、以数字衣橱为资产中台、以 AI 搭配和购买补齐为输出的抖音 AI 助手。

用户在现有抖音式 Feed 中暂停视频，用带炫彩拖尾的圈选手势选择一件单品、多个局部或整套穿搭。圈中主体会从画面中视觉抬升，用户直接对主体左滑放弃、右滑保存，不经过分析卡片，也不等待 AI 返回。

保存后，后台异步完成：

- 选区细化与主体分割。
- 整套穿搭的单品拆解。
- 单品分类、属性标签、自然语言描述与相似向量。
- Look 中单品关系和搭配逻辑分析。
- 来源、所有权、商品与购买状态管理。

数字衣橱延续 StyleCapture 的紫粉像素视觉和图鉴式体验。像素小人作为 Look 的缩略图、分享卡和社交锚点；点击后展示原始穿搭、真实单品、搭配逻辑和真人试穿，避免像素表达磨平服装细节。

用户可以输入“周五面试”“下雨天通勤”“围绕这件外套搭配”等场景或需求。系统优先使用 owned 衣橱，随后考虑已收藏或想买的单品；无法配齐时再补充商品候选，并生成一份“补齐这套”购买清单。每次返回 3–4 套有明显差异、可以局部替换的方案。

### 产品目标

- 让 Feed 中的穿搭兴趣以最低打扰成本沉淀为长期数字资产。
- 让用户能清楚区分“我有的”“我收藏的”“我想买的”“已购买待收货的”。
- 用用户自己的衣橱优先完成场景化搭配。
- 把缺失单品转化为可解释、可聚合的购买需求。
- 用真实单品图与真人试穿支持判断，用像素 Look 支持浏览和传播。
- 让 H5、Skill/Agent 和 Playground 使用同一套真实服务、合同与 Workflow。
- 把衣物入库、衣橱、搭配、渲染和购买补齐沉淀为版本化 API，使项目内各端与未来获授权的外部调用方都能复用。

### 核心体验原则

- 保护 Feed：圈选和保存不等待 AI，不强制跳转，不连续追问。
- 先保存意图，再异步理解：处理状态是产品的一部分。
- Item 是唯一单品事实；Look 只保存关系。
- 来源和所有权是两个维度，不能混成一个标签。
- 相似不等于相同；不确定时不自动合并。
- 结构化标签和自然语言描述并存。
- 真实衣物判断使用真实图，像素图只做入口和传播。
- 运行时不使用 mock/stub 冒充 AI 成果。

### P0 主链路

1. 用户进入可自由滚动的抖音式 Feed。
2. 用户暂停一条穿搭内容，圈选单件、同帧多个局部或整套穿搭。
3. 圈中主体抬升，用户直接左滑放弃或右滑保存并继续刷 Feed。
4. 用户也可以从相册上传或拍照，选择“我的衣服”或“穿搭灵感”。
5. 后台异步创建 Capture；按意图创建 Item 或 Look，并完成拆解、打标和入库。
6. 用户进入 StyleCapture 风格数字衣橱，看到 processing 到 ready 的真实状态变化。
7. 用户输入场景或需求。
8. 系统从衣橱生成 3–4 套方案，并解释搭配逻辑。
9. 用户点击方案，查看真实单品与真人试穿/明确降级的单品拼贴。
10. 用户局部替换不满意的单品。
11. 系统列出缺失单品并形成“补齐这套”清单。
12. 用户保存最终 Look；像素封面异步生成。
13. Demo Feed 提供至少 30 条有来源记录的多样化公开视频/图文样本供自由浏览，并保留固定回归子集。

### P1 能力

- 用户真人参考照与真实试穿。
- 相似 Item 提醒与受控合并。
- 电商 Offer、尺码/颜色确认、购买待收货到 owned 的状态迁移。
- 更多失败恢复、人工纠正和批量整理。

### Bonus

- 像素 Look 分享卡。
- 像素到真人的展示转场。
- 基于 Look 的轻动画或社交玩法。
- 用户形象进一步定制。

## User Stories

1. As a Feed 用户, I want to pause a clothing video, so that I can interact with the exact frame that inspired me.
2. As a Feed 用户, I want to freely circle one garment, so that I can express a visual target that is difficult to describe with keywords.
3. As a Feed 用户, I want to circle multiple local garments in the same frame, so that I can save several items without restarting the interaction.
4. As a Feed 用户, I want to circle an entire person or outfit, so that the system understands I care about the whole styling relationship.
5. As a Feed 用户, I want a colorful lasso trail, so that the visual search interaction feels distinctive and demonstrable.
6. As a Feed 用户, I want the selected subject to lift visually from the frame, so that I clearly understand what will be acted upon.
7. As a Feed 用户, I want to swipe the lifted subject directly rather than operate a card, so that the interaction feels physical and immediate.
8. As a Feed 用户, I want to swipe left to reject, so that I can dismiss a mistaken or unwanted selection without extra confirmation.
9. As a Feed 用户, I want to swipe right to save, so that I can capture inspiration with one decisive gesture.
10. As a Feed 用户, I want save confirmation to be lightweight, so that I can continue watching content without a forced navigation.
11. As a Feed 用户, I want AI processing to happen after saving, so that model latency does not block the Feed.
12. As a Feed 用户, I want an optional reason chip after saving, so that I can tell the system what I liked without being forced to type.
13. As a Feed 用户, I want to skip the reason input, so that saving remains fast.
14. As a user with poor connectivity, I want a clear accepted/processing state, so that I do not repeat the save and create duplicates.
15. As a user, I want repeated network submissions to be idempotent, so that one gesture creates one asset.
16. As a user, I want each saved asset to retain its source video, timestamp and original frame, so that I can trace where it came from.
17. As a user, I want my rough selection preserved if fine segmentation fails, so that my save is not lost.
18. As a user, I want a partial result when only some garments are confidently recognized, so that reliable work is not discarded.
19. As a user, I want uncertain hidden garments to remain pending, so that the system does not invent clothing that is not visible.
20. As a wardrobe user, I want a full outfit to be registered as a Look, so that I can retrieve the mood and relationship I originally liked.
21. As a wardrobe user, I want the garments inside a Look to also become individual Items, so that I can reuse them in new combinations.
22. As a wardrobe user, I want the same Item to appear in multiple Looks without duplication, so that my asset library stays coherent.
23. As a wardrobe user, I want the system to analyze color, silhouette, layering and material relationships in a saved Look, so that future recommendations can learn from more than coarse style labels.
24. As a wardrobe user, I want my optional “why I like it” comment stored with the Look, so that preference learning reflects my intent.
25. As a wardrobe user, I want imported Items categorized into understandable groups, so that I can browse tops, bottoms, dresses, shoes and accessories quickly.
26. As a wardrobe user, I want deeper technical categories behind the simple navigation, so that recommendation logic can distinguish layers and garment roles.
27. As a wardrobe user, I want each Item tagged with visible attributes, so that I can filter by color, material, pattern, fit and detail.
28. As a wardrobe user, I want inferred style, season and occasion tags kept separately from visible facts, so that uncertain AI interpretation is transparent.
29. As a wardrobe user, I want natural-language descriptions as well as tags, so that I can search in my own words.
30. As a wardrobe user, I want field-level confidence and provenance, so that one uncertain material guess does not invalidate an otherwise correct Item.
31. As a wardrobe user, I want my manual edits protected, so that later AI enrichment never overwrites my corrections.
32. As a wardrobe user, I want similar Items suggested rather than automatically merged, so that visually close but different garments remain distinct.
33. As a wardrobe user, I want to confirm a duplicate merge later, so that Feed saving is not interrupted.
34. As a wardrobe user, I want to upload an individual garment photo, so that I can digitize clothes I own.
35. As a wardrobe user, I want to upload a full-body photo, so that it can be decomposed into Items and optionally retained as a Look.
36. As a wardrobe user, I want to choose whether an upload is “my clothes” or “inspiration,” so that source and ownership are correctly represented.
37. As a wardrobe user, I want to take a photo directly, so that wardrobe onboarding does not depend on existing gallery images.
38. As a wardrobe user, I want to see processing, ready, partial and error states, so that the product never pretends unfinished AI work is complete.
39. As a wardrobe user, I want failed assets to be retryable, so that transient provider errors do not force a new upload.
40. As a wardrobe user, I want the digital wardrobe to use the familiar StyleCapture pixel-purple visual language, so that the product retains its identity.
41. As a wardrobe user, I want Look thumbnails represented by a fixed pixel character wearing the outfit, so that browsing feels consistent and shareable.
42. As a wardrobe user, I want to open a pixel thumbnail and see the original real outfit, so that garment detail is not lost.
43. As a wardrobe user, I want the detail view to show every real Item in the Look, so that I can understand exactly what the outfit contains.
44. As a wardrobe user, I want to know whether each Item is owned, collected, wanted or pending delivery, so that digital and physical assets are not confused.
45. As a shopper, I want a purchased Item to remain pending until receipt, so that the wardrobe does not treat undelivered goods as wearable.
46. As a shopper, I want a received purchase to become owned without recreating the Item, so that history and preference remain connected.
47. As a user, I want to enter a natural-language scene such as “Friday interview,” so that I can request an outfit without learning filters.
48. As a user, I want to add style or comfort constraints, so that recommendations respect more than the event name.
49. As a user, I want to anchor a request on one Item, so that I can ask how to style something I own or want to buy.
50. As a user, I want the system to prioritize owned clothing, so that recommendations help me use what I already have.
51. As a user, I want collected Items considered after owned Items, so that the system can explore my aspirational style without pretending I own everything.
52. As a user, I want commerce Items introduced only for missing slots, so that recommendations do not become disguised advertising.
53. As a user, I want 3–4 distinct outfit plans, so that I have meaningful choices rather than minor variations.
54. As a user, I want each plan to explain its styling logic, so that I can learn why the combination works.
55. As a user, I want hard conflicts such as dress versus top/bottom combinations rejected, so that generative reasoning cannot bypass garment structure.
56. As a user, I want weather, season and formality constraints enforced, so that visually attractive but impractical outfits are excluded.
57. As a user, I want to replace one garment in a plan, so that I can refine rather than restart.
58. As a user, I want only the affected slot to be recalculated after a replacement, so that approved parts of the plan stay stable.
59. As a user, I want replacement candidates from my wardrobe first, so that editing still respects asset reuse.
60. As a user, I want a real-item collage to appear before expensive image generation finishes, so that the recommendation is immediately inspectable.
61. As a user with a reference photo, I want to see a generated full-outfit try-on, so that I can judge the overall effect on a consistent person.
62. As a user without a reference photo, I want a fixed model or item collage rather than a fake personalized result, so that the product is honest.
63. As a user, I want try-on failures clearly downgraded to collage, so that I do not mistake a fallback for a completed try-on.
64. As a user, I want the try-on result linked to its exact Item inputs, so that I can tell which garments were rendered.
65. As a user, I want the pixel cover generated from the completed Look, so that it represents the actual outfit relationship.
66. As a user, I want pixel generation to happen asynchronously, so that saving and recommendation are not delayed.
67. As a user, I want to save a generated OutfitPlan as a Look, so that AI-created combinations join the same wardrobe system.
68. As a user, I want generated and Feed-saved Looks visibly distinguished, so that provenance is clear.
69. As a shopper, I want to see which plan Items I already own and which are missing, so that I can estimate purchase effort immediately.
70. As a shopper, I want all missing Items collected into one “complete this look” list, so that I do not revisit separate videos one by one.
71. As a shopper, I want to confirm color and size before following purchase links, so that the list reflects purchasable variants.
72. As a shopper, I want unavailable commerce data represented as a search need rather than invented stock, so that recommendations remain trustworthy.
73. As a shopper, I want the purchase list preserved, so that I can return after leaving the product.
74. As a shopper, I want completed purchases to feed back into ownership state, so that recommendations improve after shopping.
75. As a user, I want my save, reject, replacement and purchase actions to update preference signals, so that the system learns from behavior.
76. As a user, I want collected Looks to weigh more heavily for aspirational style than accidental owned clothes, so that recommendations reflect taste as well as history.
77. As a user, I want owned Items to weigh more heavily for immediate availability, so that recommendations remain practical.
78. As a user, I want to delete my source images and reference photo, so that I control sensitive personal data.
79. As a user, I want my wardrobe private by default, so that personal clothing and body information are not exposed.
80. As a user, I want to share a pixel Look without sharing my private reference photo, so that social output is privacy-preserving.
81. As a judge, I want to freely browse the Feed and perform the visual interaction, so that the demo proves a real user-triggered scenario.
82. As a judge, I want to observe the asynchronous asset state change, so that the demo does not hide model latency behind a fake result.
83. As a judge, I want a Playground trace of the Workflow, so that I can see recognition, normalization, recommendation branches and fallback decisions.
84. As a judge, I want the H5 and Skill/Agent to call the same service, so that the project is more than a front-end script.
85. As a judge, I want a complete path from visual input to wardrobe to recommendation to purchase completion, so that the scenario demonstrates business value.
86. As a developer, I want shared versioned contracts, so that frontend, backend, workers and Skill do not drift.
87. As a developer, I want every asynchronous job idempotent and traceable, so that retries do not corrupt assets.
88. As a developer, I want every model output schema-validated, so that free-form AI output cannot write invalid product data.
89. As a developer, I want provider adapters, so that changing a VLM or image provider does not rewrite business logic.
90. As a developer, I want GPU pipelines isolated from the core API, so that CUDA conflicts and long inference do not destabilize user-facing services.
91. As a developer, I want real results content-addressed and cached, so that repeated demo requests are fast without hardcoded responses.
92. As a developer, I want test fakes confined to automated tests, so that production and demo environments cannot silently return synthetic fixtures.
93. As a product operator, I want model, prompt, taxonomy and embedding versions recorded, so that asset changes are explainable and reprocessable.
94. As a product operator, I want failed tasks and provider latency observable, so that the system can be tuned before scale.
95. As a product operator, I want source and copyright provenance retained, so that content can be withdrawn or reprocessed responsibly.
96. As a future commercial operator, I want non-commercial components gated from production builds, so that prototype licensing does not silently become commercial risk.
97. As an internal client developer, I want H5, Skill and operations tools to use the same versioned API, so that product behavior does not drift across clients.
98. As an authorized API consumer, I want documented Garment Ingest, Outfit Planning and asynchronous Render APIs with stable errors, so that the capabilities can be reused without copying internal code.
99. As a platform operator, I want provider details hidden behind domain APIs, so that models and GPU platforms can change without breaking consumers.

## Implementation Decisions

### Product and frontend

- Build one React/Vite mobile application with two isolated experience domains.
- Reuse the existing Douyin-style Feed container as the source-browsing and interaction surface.
- Reuse the StyleCapture wardrobe visual language, information architecture, character assets and pixel identity.
- Do not embed one application inside another; share routing, authentication, API client and task state.
- Use SVG/Canvas for the lasso trail and mature motion primitives for subject lift and direct horizontal drag.
- Treat 600–800ms without another closed lasso as the end of a multi-selection group.
- Do not show AI analysis, match scores or similar-item results before save.
- Persist save intent first; all expensive understanding is asynchronous.
- Do not force a route change after saving from Feed.
- Use server-state caching/retry tooling rather than hand-written request state.
- Use SSE for task progress and existing trace events.

### Domain model

- Use Capture as immutable input provenance.
- Use Item as the unique garment asset and Look as an Item relationship graph.
- Keep source type separate from ownership state.
- Use field-level confidence and provenance for AI tags.
- Protect manual values from subsequent automatic enrichment.
- Preserve uncertain Look components without inventing confident Items.
- Represent preferences as events rather than mutating Item facts.
- Separate Item from CommerceOffer.
- Represent collage, try-on, pixel cover and future animation as RenderArtifact.
- Support content hashing, model versions and schema versions for every derivative.

### Visual ingestion

- Use FFmpeg for exact frame extraction; do not build a video decoder.
- Use the user’s lasso as a segmentation prompt, not as the final mask.
- Use SAM2 for image/video mask refinement and short temporal context.
- Use Grounded-SAM2 integration patterns for open-vocabulary garment candidates inside a full Look.
- Use LiteLLM as the server-side model gateway. Initial aliases map vision understanding to `doubao-seed-2-0-lite-260428`, general reasoning to the configured Ark endpoint, and image generation to `doubao-seedream-5-0-260128`; concrete names remain inside infrastructure configuration.
- Keep Qwen3-VL as an open/self-hosted vision alternative behind the same capability contract.
- Normalize VLM output through a stable taxonomy and schema validation.
- Use Shopify Product Taxonomy as a base vocabulary, extended with fashion-specific functional categories and Chinese display labels.
- Use FashionSigLIP for apparel image/text embeddings.
- Use perceptual hashes and embeddings for similarity; never equate similarity with identity by default.

### Asset backend

- Use FastAPI as a modular monolith.
- Treat FastAPI/OpenAPI as a first-class product surface rather than an implementation detail.
- Reuse the existing API, contract, Agent/Skill, Playground and trace skeleton.
- Adapt the open-source wardrobe project’s SQLAlchemy models, migrations, async tagging lifecycle, provider boundary and guarded updates.
- Do not run that project as a separate service and do not adopt its frontend.
- Use PostgreSQL for product data and pgvector for embeddings.
- Use Redis + Celery for durable asynchronous jobs, retries and GPU concurrency control.
- Use S3-compatible object storage, mapping to Tencent COS for the current domestic deployment.
- Exchange object keys between services rather than large Base64 payloads.
- Use idempotency keys for user mutations.
- Enforce feature-local `domain/application/infrastructure/interface` boundaries; domain and application code must not import LiteLLM, FastAPI, SQLAlchemy, Celery, React, or provider payload types.
- Keep HTTP handlers, workers, UI and Skill entry points thin and route all business behavior through typed application use cases.
- Add static dependency checks and reject generic dumping grounds such as unowned `utils`, `helpers`, `common`, or `manager` modules.

### API product surface

- Expose product capabilities through stable versioned APIs shared by H5, mini-program clients, Skill/Agent, internal tools and later authorized callers.
- Keep one Product API and one private Worker API over the same domain implementation; do not build a separate Partner platform for the demo.
- Publish OpenAPI documentation and generate the frontend TypeScript client from the same schemas; provide concise Python/cURL examples for other callers.
- Represent long-running work as `202 Accepted` jobs with query and SSE completion modes.
- Use pre-signed upload URLs and object keys rather than moving large image/video payloads through every service.
- Use normal user sessions for product access and scoped service keys for private Worker calls.
- Enforce user-level data isolation, upload limits and GPU queue concurrency without building multi-tenant billing or partner quota systems.
- Require request IDs and idempotency keys for mutations; return trace IDs and stable machine-readable errors.
- Keep model/provider names private to the implementation; external contracts describe garment, wardrobe, outfit and render capabilities.
- Package Garment Ingest, Wardrobe, Outfit Planning, Render, Commerce Completion and Trace as reusable API domains.
- Do not expose database tables as public resources or let external callers directly control internal model prompts.

### Recommendation Skill

- Parse scenario, weather, style, formality, comfort and anchor-Item constraints.
- Retrieve in order: owned, collected/wanted, commerce.
- Combine vector retrieval with SQL filters.
- Apply deterministic garment-slot, layering, season, formality and conflict rules before generative ranking.
- Produce 3–4 meaningfully different complete plans.
- Use LLM/VLM only for aesthetic reranking and explanation after hard constraints.
- Recalculate only the changed slot on a user replacement.
- Expose missing slots explicitly and create a purchase list from them.
- Share the same Skill service across H5, Agent and Playground.

### Rendering

- Use real Item collage as the deterministic, immediate outfit visualization.
- Keep try-on behind one provider contract. During development, use a real hosted provider or a genuinely runnable lightweight local provider so implementation is not blocked by GPU-server availability.
- Keep FastFit as the preferred self-hosted multi-reference full-look candidate for the non-commercial demo and FASHN VTON 1.5 as the preferred self-hosted single-garment candidate; activating either heavy provider is a deployment decision, not a prerequisite for building the product path.
- Isolate each GPU pipeline in a pinned custom container.
- When heavy providers are enabled, run their containers on one GPU server and serialize jobs through the queue; do not require a second compute server for the demo.
- Cache only outputs of real prior jobs by content hash; surface cached status.
- Fall back to a clearly labelled real-item collage when try-on fails.
- Reuse the existing StyleCapture pixel provider router and character system for Look covers.
- Generate pixel covers from a completed Look visual, not from coarse tags.
- Do not treat generated images as Item facts.

### Deployment and operations

- Server provisioning is explicitly deferred until the product slices are implemented and the actual model set has been measured. Issues 1–5 must continue without a rented GPU server.
- The development Compose profile runs H5, API, PostgreSQL/pgvector, Redis/Celery and normal workers locally. Optional AI providers use real hosted endpoints or lightweight local models through the same contracts; runtime mock/stub output remains prohibited.
- Keep the portable core in Docker Compose with explicit health checks, named volumes and resource limits. Heavy VLM/try-on providers use optional profiles and must not run on the laptop by default.
- During long local work, monitor CPU, memory pressure, thermal state, swap, disk and container usage; serialize work or move it to a hosted provider rather than sustaining full-machine load.
- Deploy H5, API, PostgreSQL/pgvector, Redis/Celery and model containers through one Docker Compose project on one GPU server.
- Treat one NVIDIA L40S/RTX 6000 Ada/A6000 48 GB GPU, 16 vCPU, 64 GB RAM and 300–500 GB NVMe as the safe upper recommendation only if the selected heavy providers require it. Measure first; a lighter host or hosted inference is acceptable when it passes the same real-provider evidence.
- Run SAM2/Grounded-SAM2, FashionSigLIP, FastFit and FASHN in separate containers on that host, with GPU concurrency set to one for heavy jobs.
- Keep source media and generated artifacts in Tencent COS so the server disk and network are not the media origin.
- Use a configurable Chinese multimodal API as the default VLM; the server has enough headroom to run a compact self-hosted VLM as a fallback, but the product contract does not depend on it.
- A 24 GB GPU server is a budget fallback only when the VLM remains external and heavy models are loaded serially; it is not the “one machine supports everything” recommendation.
- The existing 4 vCPU / 8 GiB CPU host is not part of the required demo topology once the GPU server is rented; it may be retired or retained only as a temporary development/backup host.
- Reuse existing trace and Playground support before adding another observability platform.
- Store provider keys only in secret management and never in client code.
- Inject Volcengine/Ark credentials only into the server-side model gateway; never place them in the repository, Feed fixtures, client bundle, traces or logs.
- Do not log raw images, face references, Base64 payloads or durable signed URLs.

### Runtime truthfulness

- Runtime and judging environments must not use mock/stub or prompt-keyed fixtures as business results.
- Feed seed items may be manually pre-tagged for browsing and regression without API calls, but every annotation must carry `curated_seed` provenance and cannot be reported as live/cached AI evidence.
- New uploads, camera inputs and uncached Feed selections must invoke the real configured provider when AI processing is enabled; Codex is not part of the runtime inference path.
- Automated tests may use provider fakes through the real provider interface.
- Processing, partial, retry and error states must be visible and recoverable.
- Cached outputs must be produced by a real previous run and traceable.
- If commerce data is unavailable, return missing slots and search queries rather than fabricated products.
- If a user lacks a reference photo, do not claim a fixed model render is personalized.

### Reuse boundaries

- Directly reuse the Feed application skeleton and its state/trace contracts.
- Migrate and adapt StyleCapture wardrobe screens and assets rather than redesigning them.
- Adapt wardrobe backend models and job patterns rather than implementing asset CRUD and tagging lifecycle from scratch.
- Wrap SAM2, Grounded-SAM2, FashionSigLIP, FastFit and FASHN VTON; do not reimplement their model internals.
- Use package-managed FFmpeg bindings/tooling, scene detection, pgvector, Celery, query caching and motion libraries.
- Do not adopt old Polyvore repositories as the production recommendation engine.
- Do not introduce a second vector database, heavyweight workflow engine, ComfyUI business layer or early microservice split.

### Priority

- P0: unified H5, single/multi/full-look Feed save, upload/camera, real async ingest, wardrobe, scene request, 3–4 plans, edit, purchase list, shared Skill/Playground and trace.
- P1: real-person reference, try-on robustness, similarity review, commerce state integration and richer failure recovery.
- Bonus: pixel share assets, transitions, animation, social loops and avatar customization.

## Testing Decisions

### Test philosophy

- Test externally visible behavior and domain contracts, not internal implementation details.
- Prefer one high-level vertical seam over separate fake demos for each module.
- The principal acceptance seam is:

  `Capture accepted -> Item/Look processing -> wardrobe ready -> OutfitPlan generated -> RenderArtifact succeeded or honestly degraded -> purchase list available`

- Every completion claim requires a fresh real smoke result and trace, not only unit tests.

### Contract tests

- Validate all API request and response schemas.
- Verify Python and TypeScript contracts agree on enums, optional fields and state transitions.
- Verify the generated TypeScript client compiles and the documented Python/cURL examples complete the happy path against the same OpenAPI contract.
- Reject unknown fields, invalid taxonomy IDs and impossible ownership transitions.
- Verify idempotency returns the original resource.
- Verify model and schema versions are present in processed outputs.
- Verify stable error codes, user data isolation and private Worker credentials.

### Domain tests

- Verify Capture provenance survives Item deduplication.
- Verify one Item can belong to multiple Looks.
- Verify a Look can remain partial when some components are uncertain.
- Verify source and ownership evolve independently.
- Verify manual edits are never overwritten by automatic tagging.
- Verify similar Items are not auto-merged below the strong-evidence gate.
- Verify purchase lifecycle moves wanted to purchased_pending to owned.
- Verify deleting a sensitive source removes accessible derivatives according to policy.

### Workflow tests

- Verify owned Items are selected before collected and commerce Items.
- Verify missing garment slots create a purchase need.
- Verify dresses conflict with simultaneous top/bottom plans when the taxonomy marks them as exclusive.
- Verify season, weather, formality and user exclusions are enforced.
- Verify four outputs are meaningfully different rather than reordered duplicates.
- Verify replacing one slot preserves accepted slots.
- Verify preference signals use distinct availability and taste weighting.
- Verify LLM/VLM output cannot bypass deterministic hard constraints.

### Worker tests

- Verify enqueue, retry, timeout, cancellation and dead-letter behavior.
- Verify duplicate jobs do not create duplicate assets.
- Verify partial segmentation/tagging writes only reliable fields.
- Verify late error callbacks cannot overwrite a completed user-corrected Item.
- Verify object keys and signed URL handling.
- Verify provider failures map to stable product states.
- Verify model version changes trigger controlled re-enrichment.

### Frontend tests

- Run mobile E2E for Feed scrolling, pause, lasso, subject lift, left reject, right save and resume.
- Save screenshot evidence for every changed initial, interaction, processing, success, failure and recovery state; DOM assertions alone are not visual acceptance.
- Verify multiple local lassos group correctly after the inactivity window.
- Verify full-person selection creates a Look-oriented save.
- Verify save does not wait for AI and does not force navigation.
- Verify task state updates appear in the wardrobe.
- Verify the StyleCapture theme remains isolated from Feed styling.
- Verify scene request, plan list, detail, slot replacement and purchase list.
- Verify pixel covers open the corresponding real Look.
- Verify accessibility for non-gesture alternatives where required.

### Visual tests

- Compare key mobile screenshots for Feed fidelity and StyleCapture wardrobe fidelity.
- Validate the lasso trail, lift depth, mask edge, drag threshold and cancel/success motion.
- Validate original Item images remain legible in Look detail.
- Validate pixel character identity remains stable across multiple Looks.
- Validate failure and processing states look intentional rather than broken.

### Real-provider acceptance

- Use at least one real Feed video frame and one real user-uploaded image.
- Run real frame extraction, segmentation, VLM tagging, taxonomy normalization, embedding and database persistence.
- Generate at least one real 3–4 plan result from the stored wardrobe.
- Run at least one real multi-reference or single-garment try-on through the provider contract; during development this may be a hosted or lightweight provider, while self-hosted heavy-provider acceptance belongs to the deployment Issue.
- Generate at least one real pixel Look cover.
- Preserve the trace, model versions and artifacts for judging and regression comparison.
- A cached repeat is acceptable only after the real first run is evidenced.

### License and deployment tests

- Verify all reused projects have recorded source, revision and license.
- Fail a production-mode build if the non-commercial FastFit provider is enabled.
- Verify GPU containers build independently with locked dependencies.
- Verify the core API starts without importing CUDA/model packages even though it is deployed on the same host.
- Verify the single-host Compose stack becomes healthy from a clean server and completes one real end-to-end job.
- Verify storage and database backups do not include plaintext provider secrets.

## Out of Scope

- Native Douyin production integration that depends on unavailable platform-private APIs.
- Automatic purchasing without an explicit user confirmation.
- Guaranteed one-click checkout across multiple merchants.
- Exact size recommendation without authoritative garment size charts and body measurements.
- Claims that generated try-on is a physically accurate fit simulation.
- Real-time AR mirror or live video try-on.
- Full 3D avatar creation, SMPL-X body reconstruction, garment mesh extraction and cloth simulation.
- Custom face sculpting or advanced avatar creator.
- Social feed, follower graph, public wardrobe and creator marketplace.
- Autonomous fashion trend forecasting.
- Training a new foundation vision, embedding or try-on model from scratch.
- Reimplementing video decoding, segmentation, vector indexing, queues or model serving.
- Commercial use of FastFit without a separate license or replacement.
- Using the pixel avatar as the factual representation of garment detail.
- Fabricating commerce inventory, AI results or match scores when providers are unavailable.
- Public partner onboarding, public SDK lifecycle, signed webhooks, tenant billing and quota management.

## Further Notes

### Success signals

The demo and subsequent pilot should instrument:

- Feed pause-to-selection rate.
- Selection-to-right-swipe save completion.
- Save interaction latency independent of AI completion.
- Asset processing success, partial and retry rates.
- Time from accepted Capture to useful Item/Look.
- Percentage of OutfitPlans fully satisfied by owned Items.
- Missing-slot click-through and purchase-list completion.
- Plan save, replacement and rejection behavior.
- Return visits to wardrobe and reuse of previously saved Items.
- Pixel share generation and share intent.
- Skill/Agent task completion and trace completeness.

Initial evaluation should prioritize task completion and trust over raw AI confidence. No target percentage should be presented publicly until measured on the actual demo corpus.

### Demo narrative

The judge should see one uninterrupted story:

1. Browse the Douyin-style Feed.
2. Pause and circle a full outfit.
3. Swipe the lifted outfit right and continue browsing.
4. Open the StyleCapture wardrobe and see the Look and Items complete asynchronously.
5. Ask for an outfit for a concrete scene.
6. Compare 3–4 plans and open a detail view.
7. Replace one garment.
8. View a real try-on or clearly labelled collage fallback.
9. Open “complete this look” for missing Items.
10. Save the final Look and see its pixel cover.
11. Open the Playground trace to show the same real Workflow behind the H5 and Skill.

### Product quality bar

- The experience must feel like one real product despite the two visual domains.
- Frontend and backend states must agree; no optimistic UI may claim AI completion.
- Interactions must remain fluid when model providers are slow.
- Every external capability should have a stable adapter, explicit failure state and trace.
- Open-source reuse must be coordinated through project contracts, not copied as disconnected demos.
- An Issue is complete only when its stated end-to-end acceptance criteria, tests and failure states are complete. Missing work inside the accepted scope cannot be deferred by creating a “phase 2” or follow-up Issue.

### Key risk controls

- Segmentation quality: preserve original lasso, allow partial results and use nearby frames only as evidence.
- Taxonomy drift: keep stable IDs, store raw model descriptions and version normalizers.
- Recommendation quality: combine deterministic constraints, domain embeddings and aesthetic reranking.
- Try-on instability: keep real Item collage as the deterministic baseline and isolate model providers.
- Demo latency: warm GPU workers and use content-addressed cache only after a real evidenced run.
- License risk: conditionally enable FastFit only for the non-commercial demo.
- Scope risk: keep 3D and social systems outside P0/P1.
