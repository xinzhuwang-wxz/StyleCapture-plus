# Overnight Launch Prompts

按顺序在同一个 Codex 任务中输入。三段都完成后再离开。

## 1. 创建终局 Goal

```text
请为当前 StyleCapture-plus 仓库创建一个新的终局 Goal，不设置 token budget：

交付一个可由评委真实操作、达到产品品质的移动端 AI 数字衣橱，完整满足 docs/product/PRD.md、GitHub Issues #1–#6 和 .omx/ultragoal/goals.json。按依赖顺序连续完成所有 Issues，不在 Issue 之间等待确认；使用真实数据和稳定 API，运行时禁止 mock、stub、固定结果或由 Codex 代替产品模型输出。产品推理、视觉理解和生图通过 LiteLLM 能力别名接入豆包/方舟，密钥仅在服务端；已知 Feed 素材可以由开发智能体人工预标注为 curated_seed，不调用模型 API，也不冒充实时 AI。复用现有抖音 Feed 容器、StyleCapture 衣橱视觉、像素管线和已审计开源能力，不重复造轮子。代码采用可读的 feature-local domain/application/infrastructure/interface 分层，API、前端、Worker、Skill 和数据合同保持一致。核心环境用 Docker Compose，重 AI 不在笔记本默认运行；长任务持续检查 CPU、内存压力、温控、swap、磁盘和容器占用，触发保护条件就降并发或停止昂贵任务。每个可见里程碑都必须从真实用户角度在移动浏览器完整操作，保存交互、processing、success、failure、recovery 截图和 trace，经过 fresh tests、视觉、架构、安全、隐私和代码质量审查并修复 P0/P1。自主管理分支、commit、push、PR、merge、Issue、ExecPlan 和 ADR。只有所有 Issue 关闭或有等价证据、所有 P0 主链端到端可演示、最终独立审查为 APPROVE + CLEAR 且无 P0/P1 遗留时，Goal 才完成。
```

## 2. 启动连续工程 Loop

```text
现在启动 StyleCapture-plus 连续工程 Loop，并持续运行到当前 Goal 完成。先读取 AGENTS.md、PLANS.md、CONTEXT.md、docs/product/PRD.md、docs/architecture/TECHNICAL-DECISIONS.md、docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md、docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md、docs/adr/ 和 .omx/ultragoal/，再读取 GitHub Issues/PR。选择第一个未阻塞 Issue，维护 living ExecPlan，完成一个可验证的纵向切片；测试、真实移动端操作、截图/trace、视觉审查、代码/安全/架构审查、清理和复验全部通过后再合并，并立即进入下一 Issue。发现当前验收缺口就在当前 Issue 修复；跨切片长期决策写 ADR 并同步相关 Issue；只有真正独立的工作才新增 Issue，不能用新 Issue 留尾巴。开发期间优先复用 _ref 和成熟开源能力，保持 Docker 可迁移性和笔记本资源保护。若 macOS 需要保持本地任务运行，可启动低开销 keep-awake，并在 Goal 完成或停止时清理。除不可逆、凭据受限的外部生产操作或真正改变产品方向的选择外，不要停下来询问。
```

## 3. 创建同线程每小时 Heartbeat

```text
请在当前 Codex 任务上创建并立即启用一个名为“StyleCapture 每小时质量巡检”的 Heartbeat automation，每小时运行一次，不创建独立开发任务或并发分支。每次运行执行以下提示：

审计当前 StyleCapture-plus Goal、.omx/ultragoal 状态、GitHub Issue/PR、living ExecPlan、ADR、最近提交和 diff、测试输出、trace、真实移动端操作与截图证据。检查是否偏离 Goal，是否缺少验收证据，是否存在 hidden mock/fixed result、curated_seed 被冒充 AI、新用户输入绕过 LiteLLM、密钥或 provider 细节泄漏、前后端/合同/任务状态漂移、跨层依赖、万能 utils、重复或废弃代码、视觉和失败恢复问题，以及是否错误等待 GPU 服务器。检查 CPU、内存压力、温控、swap、磁盘和 Docker 用量；资源压力过高时停止重复进程、降并发或把重能力移到托管 provider。可运行时必须亲自按移动端用户路径操作并核对截图。安全且属于当前范围的 P0/P1 立即修复并复验；必要时修订当前 Issue/ExecPlan，长期跨切片决策写或更新 ADR，只有独立价值才新增 Issue。完成巡检后恢复连续工程 Loop。只报告实质纠正、真实 blocker 或简洁的 clean audit；Goal 完成后禁用此 Heartbeat。
```

## 离开前

- 保持电源连接、Codex 运行、网络可用。
- 本地任务需要持续运行时不要合盖；macOS 合盖后本地 Docker、浏览器测试和 Heartbeat 可能暂停。
- 不需要预先准备 GPU 服务器或豆包 API key；凭据受限的 live smoke 留在明确验收点，不能阻塞其余真实产品链路。
