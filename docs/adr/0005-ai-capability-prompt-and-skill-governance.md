# ADR-0005: AI Capability 统一 Prompt、Workflow 与 Skill

- Status: Accepted
- Date: 2026-07-26

## Context

StyleCapture 同时包含服装识别、整套分析、穿搭推荐、实物转像素、照片转像素、
真人试穿和像素封面等智能能力。多数能力只有一次模型调用，少数能力包含上传、
后台任务、逐套产出、持久化和失败恢复。若把每条 Prompt 都包装为 Skill，会产生
没有业务价值的重复层；若只把 Prompt 留在 Provider 内，又会让后续队友难以发现、
复用、评测和安全升级。

仓库已经通过 LiteLLM 能力别名隔离具体模型，并在多个 Provider 中记录
`prompt_version`、`schema_version` 和 taxonomy 版本。现有
`scene-outfit-matching` Skill 也已经证明：Skill 可以只调用 Product API，而无需
持有 Prompt、模型 ID 或 Provider 密钥。

## Decision

1. 统一管理单位是 **AI Capability**，不是 Prompt 或 Skill。每项能力具有稳定的
   `capability_id`、产品输入输出、持久化语义、能力别名、Prompt/Schema/Taxonomy
   版本、超时与重试策略、评测样例和负责人 feature。
2. Prompt 继续按 feature 就近维护，并且只存在于基础设施实现中。Prompt 修改必须
   更新 `prompt_version`；结构化响应变化必须更新 `schema_version`；影响缓存或派生
   产物的修改还必须更新输入签名。
3. LiteLLM 是产品推理、视觉理解和通用图像生成的唯一模型网关。应用层只传能力
   别名；具体豆包/方舟 Endpoint、密钥和 payload 只存在于服务端配置与适配器。
4. Skill 是产品级 Capability 的可选 API facade：只有用户/Agent 能独立调用的完整
   目标才提供 Skill。Skill 只能调用版本化 Product API，禁止复制 Prompt、直接调用
   LiteLLM 或持有 Provider 密钥。
5. 单节点模型调用不为了形式统一而创建 Skill。多步骤流程继续由 feature-local
   Application Use Case、任务队列和现有 trace 编排；在出现真正分支/补偿复杂度前，
   不引入 LangGraph 等新的工作流框架。
6. Promptfoo 作为离线/CI 评测工具，而不是运行时 Prompt 管理器或业务编排器。
   评测必须尽量从 Product API 进入，以覆盖生产同款 LiteLLM、Schema、状态机和
   持久化边界。图像能力还必须保留真实移动端截图与视觉审查，不能只看文本 rubric。
7. Promptfoo 不进入产品镜像，也不成为核心依赖。使用固定版本的按需命令运行；
   smoke 集合用于 Prompt/别名改动，完整集合用于里程碑与部署前验证。

## Consequences

- 队友从 Capability 目录能够找到产品入口、Prompt 版本、Schema、Skill 和评测，
  而不需要理解具体模型供应商。
- Skill 与 H5、外部调用方复用同一 Product API，避免出现第二套业务逻辑或绕过
  LiteLLM 的模型调用。
- 单节点能力保持轻量；复杂度只在真实 Workflow 中出现。
- Promptfoo 会产生真实模型费用，完整评测不能进入每次本地单元测试；必须分为低成本
  smoke 与部署前 full 两档，并记录缓存命中、延迟和费用。
- FASHN 等专用非 Prompt Provider 可以继续作为 feature-local 可替换适配器，但其
  产品 Capability、状态、trace 和失败恢复仍遵守同一治理规则。

## Alternatives considered

- **所有 Prompt 都包装成 Skill。** 拒绝，因为内部单节点调用会多出无意义的 API/
  脚本层，并诱发 Prompt 和后端业务合同重复。
- **把所有 Prompt 移到一个全局目录。** 拒绝，因为 Prompt 会和 feature 的输入、
  Schema、taxonomy、任务状态及缓存签名脱节。
- **让 Promptfoo 直接调用豆包模型。** 拒绝作为主评测路径，因为会绕过 Product API、
  LiteLLM 别名、任务状态和持久化；只允许用于受控的候选模型对比。
- **引入通用 Agent/Graph 框架统一编排。** 拒绝，因为当前绝大多数能力是单节点或
  线性后台任务，现有 Application + Celery 已能清晰表达。

## Verification

- 架构测试禁止 Skill 和浏览器源码出现 Provider Endpoint、模型 ID 或密钥。
- 所有模型产物 trace 至少包含 `capability_id`、能力别名、Prompt/Schema 版本或明确的
  `not_applicable`。
- Prompt/别名修改运行对应 Promptfoo smoke；部署前运行 full 集合并保存结果。
- 移动端分别验证照片转像素、单品像素图、穿搭推荐、真人试穿和像素封面的处理中、
  成功、失败与恢复状态。

