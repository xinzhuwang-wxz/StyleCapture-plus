# StyleCapture AI Capability Catalog

本目录是智能能力的发现入口。运行时真源仍在各 feature 的 domain/application/
infrastructure/interface 模块；这里不复制 Prompt 或业务逻辑。

## 管理规则

- **Capability**：稳定的产品能力与输入输出合同。
- **PromptSpec**：feature-local 的 Prompt、版本、Schema 与评测数据。
- **Workflow**：Application Use Case + 现有任务队列/trace，负责多个 Capability 或
  确定性步骤的编排。
- **Skill**：可选的 Product API facade，供队友、Agent 或外部系统调用；不持有 Prompt。
- **LiteLLM**：通用推理、视觉和生图的唯一网关；具体模型只在服务端配置中出现。
- **Promptfoo**：离线回归与候选比较，不进入线上运行时。

## 当前能力

| Capability ID | Feature | 运行入口 | 网关/Provider | Prompt/Schema 版本位置 | Skill |
| --- | --- | --- | --- | --- | --- |
| `capture.garment_understanding` | capture | Capture Worker | LiteLLM `vision_understanding` | `capture/infrastructure/providers.py` | 内部能力 |
| `capture.visual_grounding` | capture | Whole-Look Worker | LiteLLM `visual_grounding` | `capture/infrastructure/grounding.py` | 内部能力 |
| `capture.segmentation_refinement` | capture | Capture Worker | SAM2 tiny / coarse fallback | `capture/infrastructure/feed_media.py` | 内部能力 |
| `look.outfit_analysis` | look | Look Worker | LiteLLM `outfit_analysis` | `look/infrastructure/outfit_analysis.py` | 内部能力 |
| `outfit.scene_matching` | outfit | `/v1/outfit-plans*` | LiteLLM `reasoning` | `outfit/infrastructure/reranker.py` | `scene-outfit-matching` |
| `item.pixel_presentation` | item_presentation | Item presentation API/Worker | LiteLLM `image_generation` | `item_presentation/application.py`, `processing.py` | 内部派生能力 |
| `photo.pixel_trial` | pixel_trial | `/v1/pixel-trials*` | LiteLLM `image_generation` | `pixel_trial/processing.py`, `render/pixel_card_style.py` | `pixel-character-card` |
| `look.pixel_cover` | render | Look render API/Worker | LiteLLM `image_generation` | `render/prompt_contracts.py`, `render/pixel_card_style.py`, `render/signatures.py` | 产品能力，随 Look 详情调用 |
| `look.virtual_try_on` | render | Look render API/Worker | `doubao-virtual-try-on` Skill：分析、生成、审计、重试 | `render/processing.py`, `render/infrastructure/providers.py`, `signatures.py` | 产品能力，随 Look 详情调用 |

## 版本与变更门槛

1. 改 Prompt：更新 `prompt_version`，运行 Capability smoke eval。
2. 改结构化输出：更新 `schema_version`、合同测试和 OpenAPI。
3. 改 taxonomy：更新 taxonomy 版本、迁移/兼容规则和困难案例。
4. 改图像生成语义：同时更新派生输入签名，避免旧缓存冒充新产物。
5. 新增外部可调用目标：先复用 Product API，再决定是否增加薄 Skill facade。
6. Skill、H5 和公共 API 禁止出现 Provider 模型 ID、Endpoint 或密钥。

## Promptfoo 策略

Promptfoo 只从 `evals/promptfoo/` 的固定版本命令运行。默认通过 Product API 自定义
Provider 进入真实链路。测试分两档：

- `smoke`：每项 3–5 个代表性/失败样例，适用于 Prompt、Schema 或能力别名变更。
- `full`：Feed 困难集、用户上传、整套拆解、推荐、像素保真和真人试穿，适用于里程碑
  与部署前验收。

文本/结构能力使用 JSON Schema、taxonomy、中文完整性和业务规则断言；图像能力使用
文件有效性、主体数量、服装保真、自我一致性、视觉 rubric，并继续由真实移动端截图
和人工视觉审查兜底。

## Audited Doubao try-on Skill

[`doubao-virtual-try-on`](../../skills/doubao-virtual-try-on/) remains a provider-bound,
independently installable Codex artifact, and is also the audited executor used by the server-side
`look.virtual_try_on` Worker adapter. The Product API continues to own authenticated Looks,
RenderArtifacts, privacy, persistence and honest degradation; the Skill owns its linear
understand-generate-audit-retry workflow. The standalone exception is documented in
[ADR-0006](../adr/0006-standalone-provider-bound-codex-skill.md), and the explicit product-runtime
reuse decision is documented in
[ADR-0007](../adr/0007-product-audited-doubao-try-on.md).
