# PR #12 移动端视觉融合 ExecPlan

> 当前分支：`codex/pr12-main-integration`
>
> 基线：`main@c3b29c3`
>
> 目标：吸收 PR #12 的移动端产品外壳和像素视觉，但不回退主线已经跑通的真实
> Item、Look、RenderArtifact、搭配、Feed、任务与数据库链路。

## 用户可观察结果

1. 评委从独立 Feed 入口进入小程序后，看到 PR #12 的浅色像素手机界面和四个一级页。
2. 衣橱继续展示真实 API 返回的穿搭与单品；单品保留来源、状态、编辑、删除原图和“用它搭配”。
3. AI 推荐继续通过真实 Product API 渐进返回 3–4 套结果，一套生成完成就先展示一套。
4. 穿搭详情继续使用真实 Item 图、拼贴、真人试穿、像素封面、购买清单和来源回看。
5. 拍照/相册既能作为单品或整套入库，也提供独立“试试看”：全身照生成像素小人但不写入衣橱。
6. Feed 暂停、圈选、Tag、左右滑入库与恢复原视频位置保持可用。
7. 一级页面和 Feed Tag 的单品/穿搭卡片优先展示像素派生图；进入详情、实际搭配、
   相似检索、购买和换装后仍以规范化真实图和结构化标签为准。

## 三方融合原则

- **视觉与信息架构**：相似功能优先采用 PR #12 的浅色像素风、PhoneFrame、卡片密度、
  一级导航和二级页表达。
- **业务真源**：以 `main@c3b29c3` 的生成合同和 `wardrobeApi` 为唯一真源。
- **拒绝回归**：删除 PR #12 的 `mockApi`、浏览器假 RenderPort、固定计时器产物和硬编码
  衣橱数据；策展素材只能作为明确标注的冷启动种子。
- **双层媒体**：Item/Look 的真实图是唯一真源；像素图是带输入签名、来源和状态的
  可再生展示变体。像素生成失败只影响一级卡片效果，不阻断入库或搭配。
- **并集而非覆盖**：PR #12 没有的 Feed Tag、任务恢复、来源回看、单品纠错、购买状态、
  私密试穿和失败降级必须保留。

## 实施顺序

- [x] 核对本地 `main` 与 `origin/main` 同步于 `c3b29c3`。
- [x] 审计 PR #12 的提交、页面、资产、冲突和 mock/真实边界。
- [x] 从 main 创建融合分支并以非提交 merge 保留三方差异。
- [x] 用 main 真实业务实现解决冲突，同时吸收 PR #12 PhoneFrame、导航与视觉组件。
- [x] 把衣橱、AI、分析、个人页、单品/穿搭详情改造成 PR #12 视觉下的真实 API 页面。
- [x] 增加 Item 像素展示变体：Git seed 清单幂等导入 + 新输入异步生成 + 失败回退真实图。
- [x] 增加不入库的“全身照 → 像素小人 Try”真实异步链路。
- [x] 删除运行时 mock、固定产物和重复业务合同，并增加静态防回流测试。
- [x] 按 ADR-0005 统一 AI Capability、Prompt 版本、Skill 边界与 Promptfoo 评测入口。
- [x] 跑合同生成、lint、typecheck、单元/集成、Docker 与真实移动端截图验证。
- [ ] 更新 PR #12，确认无 P0/P1 后再合并。

## 复用审计

| 能力 | 候选 | 决策 | 原因 | 来源 / 许可证 |
| --- | --- | --- | --- | --- |
| 手机外壳与一级导航 | PR #12 `PhoneFrame`；当前 `product-shell` | 适配复用 PR #12 | 已形成完整移动产品质感，且不承载业务状态 | 本仓库用户代码 |
| 浅色像素视觉 | PR #12 `pixel-theme.css` 与各 feature CSS；当前主题 | 适配合并 | 保留当前可访问/失败态选择器，仅替换视觉 token 与页面布局 | 本仓库用户代码 |
| Feed 圈选入库 | PR #12 旧 Feed props；main `FeedScreen` | 直接复用 main | main 已接真实 manifest、任务、恢复和 Tag 交互 | 本仓库用户代码 |
| 衣橱数据 | PR #12 `mockApi/catalog`；main OpenAPI client | 直接复用 main 合同，适配 PR #12 卡片 | 避免第二真源和固定结果 | `openapi-typescript` MIT |
| 自由搭配约束 | PR #12 `comboRules`；后端 outfit workflow | 复用规则作为前端即时校验，保存仍调用后端 | 前端只负责反馈，搭配真相仍由 Product API 决定 | 本仓库用户代码 |
| 搭配生成 | PR #12 mock outfits；main progressive outfit API | 直接复用 main | 真实 LiteLLM/规则/召回链路已测试 | 本仓库用户代码；LiteLLM MIT |
| Look 媒体 | PR #12 browser demo render；main RenderArtifact API | 拒绝 PR #12 demo adapter，直接复用 main | 禁止固定/计时器假 AI 与重复合同 | 本仓库用户代码 |
| Item 一级像素图 | 前端硬编码映射；Item 新字段；通用媒体变体 | 复用对象存储、Celery、LiteLLM 和输入签名，以 Item 真实 display image 派生 | 保持真实图唯一真源，同时让一级页面统一像素调性 | 本仓库用户代码；LiteLLM MIT |
| 预置像素映射 | Python 硬编码 `SEED_ITEMS`；Git manifest | 改为版本化 seed manifest，启动时幂等导入真实图和像素图 | 关联关系可审计、可扩展、可复现，不把运行 volume 当源数据 | 本仓库策展资产 |
| 照片转像素 Try | `_ref/StyleCapture-main` pixel-avatar；main render provider/job/object store | 适配旧 prompt/交互，复用当前基础设施 | 不引入本地重模型，不绕过 LiteLLM，不写入衣橱 | 用户参考代码；LiteLLM MIT |
| 上传与拍照 | PR #12 本机照片数组；main私密上传/ingest | 直接复用 main，补独立 Try 用例 | 保持隐私、任务与清理语义真实 | 本仓库用户代码 |

## 验证门槛

- H5：lint、typecheck、Vitest、production build 全绿。
- Backend：Ruff、Mypy、目标 pytest 与全量 pytest 全绿；OpenAPI 生成无漂移。
- Docker core：API、H5、PostgreSQL、Redis、worker、LiteLLM 健康；没有本地重模型。
- 390×844 实际操作并截图：
  Feed 浏览/暂停/圈选/入库/恢复、上传单品、上传整套、衣橱双视图、单品详情、
  AI 渐进推荐、保存穿搭、真实拼贴、真人试穿、像素封面、独立像素 Try、失败恢复。
- 视觉门槛：初始、交互、处理中、成功、失败、恢复状态均无溢出、错图、英文业务文案或
  mock/curated 伪装。

## Surprises & Discoveries

- PR #12 是前端信息架构重做，不是单纯换皮；它增加了大量页面，同时把多条真实链路
  换成了 `USE_MOCK = true` 和浏览器假渲染。
- 主线已经拥有 PR #12 不具备的完整 Item/Look/RenderArtifact/搭配/购买/Feed 恢复合同，
  因此正确方向是“PR #12 外壳 + main 业务核心”，不能选择任意一侧整包覆盖。
- 旧 StyleCapture-main 确有照片转像素能力；plus 当前只有 Look 关联的像素封面，
  需要新增一个明确“不入库、可自动清理”的独立 Try 用例，而不是用本地程序头像冒充 AI。
- 一级卡片像素图与详情真实图是同一 Item 的两个媒体角色，不是两件衣服；去重、搭配和
  标签都只依赖 Item 真源，不能使用像素图做视觉检索或类别判断。
- 用户上传的实物图已用真实 provider 验证：视觉理解、中文 taxonomy、Item 入库与一级
  像素展示均完成；当全身画面含多件衣服却被用户指定为“单件”时，当前后端选择保留原图
  而不擅自猜测目标衣服，AutoResearch 需继续检查这条歧义路径的提示与恢复是否足够清楚。
- Promptfoo 不能为每个 case 新建独立 demo 会话，否则会重复冷启动种子并增加主机和托管
  provider 负担；自定义 Product API provider 在单次评测进程内复用同一匿名 session。

## Decision Log

- 2026-07-26：所有冲突文件先保留 main 的真实业务版本，再逐页适配 PR #12 视觉；
  `mockApi` 与浏览器 demo render 不进入产品运行时。
- 2026-07-26：独立像素 Try 与 Look 像素封面是两个产品用例。前者输入用户全身照且不入库，
  后者输入已保存 Look 并作为封面/分享锚点。
- 2026-07-26：增加 Item 像素展示变体。预置素材通过 Git manifest 导入；用户新输入在
  规范化真实图准备好后异步生成。一级页面优先像素、详情与智能链路只用真实图。
- 2026-07-26：AI 能力以 Capability 为统一管理单位；Prompt 按 feature 就近维护，
  产品级目标可提供仅调用 Product API 的 Skill，Promptfoo 只用于真实 API 离线评测。
- 2026-07-26：Feed 点击画面进入可圈选暂停态；空点一次恢复播放。圈选键在暂停态仍常亮
  可点，前两条 Feed 同时提供可重播的非阻塞画圈手势引导。
- 2026-07-26：Promptfoo 固定为 `0.121.19`，通过 Product API 串行执行并复用会话；当前
  3 个中文成功场景与 1 个请求校验失败场景共 4/4 通过，不把评测工具加入产品镜像。

## Fresh Evidence

- Backend：Ruff 通过；Mypy `100 source files` 通过；Pytest `254 passed`。
- H5：Vitest `59 passed`；TypeScript 通过；Vite production build 通过；Skill 合同测试
  `4 passed`；OpenAPI 已从当前后端重新生成。
- Promptfoo：真实 Compose Product API，`4 passed / 0 failed / 0 errors`，并发为 1。
- Docker：API、H5、LiteLLM、PostgreSQL、Redis、light worker 均健康；真实日志包含
  `visual_grounding`、`vision_understanding`、`outfit_analysis`、图像生成和真人试穿任务。
- 手机 390×844：已实操 Feed 暂停/常亮圈选/画圈引导/整套保存、衣橱双视图、真实单品
  详情、中文 AI 推荐、真实拼贴、真人试穿、像素封面、照片像素 Try 和用户上传实物图。
- 证据截图：`docs/evidence/pr12-integration/`。
