# 码上搭：纵向 Issue 拆分草案

状态：已发布到 GitHub
来源：[PRD](./PRD.md) 与 [技术决策](../architecture/TECHNICAL-DECISIONS.md)

## 已发布 Issues

1. [#1 上传或拍照一件真实衣服并进入数字衣橱](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/1)
2. [#2 Feed 圈选单品或多个局部并直接滑动入库](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/2)
3. [#3 Feed 整套穿搭拆成 Look 与可复用 Items](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/3)
4. [#4 场景搭配 Skill 生成、替换并补齐一套穿搭](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/4)
5. [#5 为完成的 Look 生成真实拼贴、真人试穿和像素封面](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/5)
6. [#6 开发完成后部署可评审的完整产品](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/6)

## 共同完成规则

- 每个 Issue 都必须交付一条可独立演示的端到端路径，包含所需 schema、API、后台任务、UI、测试与真实运行证据。
- Issue 验收范围内发现的问题必须在原 Issue 修完；不能通过创建“第二阶段”或后续 Issue 代替完成。
- 不拆出独立的“搭脚手架”“建表”“写接口”“接模型”“补测试”等水平任务；第一条需要这些能力的纵向 Issue 负责把它们一起建好。
- 运行时和评审环境禁止 mock、stub、预计算答案或按输入返回固定结果；测试 fake 只能位于自动化测试。
- 每个 Issue 完成时必须提交测试命令、退出码、真实 trace、真实产物和仍存在的非阻塞限制。存在未解决 P0/P1 时不得标记完成。

## 1. 上传或拍照一件真实衣服并进入数字衣橱

### What to build

建立第一条真实纵向链：用户在 StyleCapture 风格 H5 中上传或拍摄一件衣服，选择“我的衣服”或“穿搭灵感”，系统异步理解并把它作为 Item 写入数字衣橱。这个 Issue 同时建立后续切片共同复用的应用骨架、领域合同、数据库、任务状态和单机 Compose 基线。

### Acceptance criteria

- [ ] 移动端支持相册与相机输入，并要求用户选择 owned 或 inspiration；取消、超限和上传失败均有明确状态。
- [ ] Product API 使用预签名上传、`202 Accepted + job_id`、idempotency key、查询/SSE 状态和稳定错误码。
- [ ] PostgreSQL/pgvector 保存 Capture、Item、来源、所有权、字段级置信度、模型版本和对象 key；Redis/Celery 执行可重试任务。
- [ ] 真实 VLM 输出经过 schema 校验和 taxonomy 归一化，真实 FashionSigLIP embedding 写入 pgvector；失败时保留 Capture 并可重试。
- [ ] StyleCapture 衣橱展示 processing、ready、partial、error；Item 详情展示真实图片、分类、属性、来源和所有权。
- [ ] 用户可纠正标签和所有权，后续自动任务不能覆盖人工值；用户可删除源图并使其不可访问。
- [ ] FastAPI OpenAPI 是合同真源，前端 TypeScript 客户端由合同生成；Python/cURL 示例可完成同一真实调用。
- [ ] 单机 Docker Compose 基线能启动 H5、API、PostgreSQL/pgvector、Redis/Celery，并完成一条真实上传 trace。
- [ ] 合同、领域、Worker、移动 E2E 和真实 provider smoke 全部通过。

### Blocked by

None - can start immediately.

### User stories covered

25–31、34–39、44–46、78–79、86–89、93–99。

## 2. Feed 圈选单品或多个局部并直接滑动入库

### What to build

在现有抖音式 Feed 中完成真实视觉交互：暂停视频后连续圈选一个或多个服装局部，炫彩轨迹闭合后主体从帧中抬升，用户直接左滑放弃或右滑保存。保存立刻恢复 Feed，后台使用真实帧、SAM2 和同一 Item 入库链完成资产沉淀。

### Acceptance criteria

- [ ] 复用现有 Feed 的滚动、播放和暂停能力；精确记录视频、时间戳、帧尺寸与归一化圈选路径。
- [ ] 圈选具有炫彩拖尾；单次闭环只做轻抬升，600–800ms 无新圈选后合并为最终主体并进入横滑状态。
- [ ] 主体而非卡片被直接拖动；左滑不创建资产，右滑立即持久化保存意图并恢复原 Feed。
- [ ] 同帧多个局部生成一批幂等 Item 任务，一次网络重试不能创建重复资产。
- [ ] 后台对真实帧执行 FFmpeg 精确抽帧和 SAM2 mask 精修；每个 Item 继续走 Issue 1 的真实打标、taxonomy、embedding 和持久化流程。
- [ ] 分割失败时保留用户粗选区，部分成功时只写入可靠 Item；UI 显示 processing/partial/retry，不丢失右滑保存。
- [ ] 可选喜欢原因在保存成功后以非阻塞快捷项出现，用户不操作即可继续刷 Feed。
- [ ] 移动 E2E、手势边界、视觉回归、幂等和一条真实视频 trace 全部通过。

### Blocked by

- [#1](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/1)

### User stories covered

1–19、32–33、75、81–82、87、91–92。

## 3. Feed 整套穿搭拆成 Look 与可复用 Items

### What to build

当用户圈选整个人或整套穿搭时，系统把原始选择注册为 Look，同时使用 Grounded-SAM2、SAM2 和 VLM 拆出可可靠识别的 Items，保存搭配关系与用户喜欢原因。数字衣橱可以从 Look 返回原视频帧、真实整套和每件真实 Item。

### Acceptance criteria

- [ ] 整套选择右滑后立即创建 Look 占位和原始 Capture，不等待拆解完成。
- [ ] Grounded-SAM2 产生服装候选、SAM2 精修 mask、VLM 归一化类别；遮挡或不确定部分以 pending component 保留，不制造虚假 Item。
- [ ] Look 只引用 Items，不复制 Item 事实；同一 Item 可属于多个 Looks，视觉相似默认不自动合并。
- [ ] Look analyzer 保存色彩、轮廓、材质、层次、视觉重心、场景与风格关系，并记录 prompt/model/schema 版本。
- [ ] 用户的可选喜欢原因与 Look 关联，并作为 PreferenceSignal 保存而非改写 Item 标签。
- [ ] StyleCapture 衣橱展示真实 Look 来源、处理状态和真实 Item 列表；像素封面未生成时显示明确 processing 状态而非不匹配的假像素图。
- [ ] Look 详情可以回到原始视频和时间点，展示来源证据与删除/撤回状态。
- [ ] 拆解、部分成功、关系一致性、跨 Look 复用、视觉页面和真实整套 trace 测试通过。

### Blocked by

- [#1](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/1)
- [#2](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/2)

### User stories covered

20–24、32–33、40、42–43、68、75–76、95。

## 4. 场景搭配 Skill 生成、替换并补齐一套穿搭

### What to build

用户在 H5 输入场景、风格、天气、舒适度或锚定 Item，系统从真实数字衣橱生成 3–4 套明显不同的 OutfitPlans。用户可以替换单个槽位、保存最终 Look，并查看 owned 与缺失商品组成的“补齐这套”清单；H5、Skill 和 Playground 调用同一服务。

### Acceptance criteria

- [ ] 同一 Outfit Planning API 接收场景、天气、风格、正式度、舒适度、必须使用和排除的 Items。
- [ ] SQL/pgvector 召回顺序为 owned、collected/wanted、commerce；商品只补缺失槽位。
- [ ] 硬规则在生成式重排前执行，能阻止连衣装与上衣/下装冲突，并执行层次、季节、天气、正式度和用户排除条件。
- [ ] 返回 3–4 套结构完整且差异可解释的方案；不能只是顺序不同或文案不同。
- [ ] H5 展示每件 Item 的来源、所有权、搭配角色和解释；真实单品拼贴立即可见。
- [ ] 替换一个槽位只重算相关候选，保留用户已接受的部分；替换仍优先用户衣橱。
- [ ] 缺失槽位形成可持久化购买清单；无真实商品 API 时输出明确搜索需求和跳转，不伪造库存、价格或同款。
- [ ] 最终 OutfitPlan 可保存为 `ai_generated` Look，购买状态按 wanted → purchased_pending → owned 演进。
- [ ] H5、Skill/Agent 和 Playground 使用同一 API、规则版本和 trace；规则、差异性、替换、购买清单和真实 smoke 测试通过。

### Blocked by

- [#1](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/1)

### User stories covered

47–59、67、69–77、83–85、97–99。

## 5. 为完成的 Look 生成真实拼贴、真人试穿和像素封面

### What to build

为 Feed 保存或 AI 生成的 Look 建立统一 RenderArtifact 链：先返回确定性的真实单品拼贴，再异步生成真人试穿和 StyleCapture 像素小人封面。所有结果与准确输入关联，失败时诚实降级，像素封面可用于衣橱浏览和隐私安全的分享。

### Acceptance criteria

- [ ] Look 详情先显示由真实 Item 图片生成的拼贴，不等待 GPU 生成。
- [ ] 统一 try-on provider 合同至少接通一个真实托管或本地轻量 provider，使无 GPU 服务器时仍可完成真实试穿；FastFit/FASHN 作为自托管重 provider 适配器保留。
- [ ] 有用户参考照时才称为用户试穿；没有参考照时使用固定模特或拼贴，并在 UI 中明确标注。
- [ ] 试穿失败、超时或类别不支持时自动降级为拼贴，不能把降级结果标成真人试穿成功。
- [ ] 复用 StyleCapture pixel provider router，从完成的 Look 视觉生成稳定角色风格的像素封面；点击像素封面能回到准确的真实 Look。
- [ ] 分享产物只包含允许公开的像素 Look 和必要文案，不包含用户参考照、私有源图或长期签名 URL。
- [ ] RenderArtifact 记录输入版本、provider、模型、参数、状态、对象 key 与内容哈希；缓存只能命中真实历史结果。
- [ ] FastFit 只在非商业 Demo 配置可启用，生产配置必须拒绝启动该 provider；没有重 GPU 时只延后其 live smoke，不延后本 Issue 的其余产品验收。
- [ ] 拼贴、至少一个真实 provider 试穿、像素生成、隐私、降级、缓存和视觉回归测试全部通过。

### Blocked by

- [#3](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/3)
- [#4](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/4)

### User stories covered

41–43、60–68、78–80、90–91、96。

## 6. 开发完成后部署可评审的完整产品

### What to build

前五条切片全部完成后，根据真实模型组合和峰值显存测量结果选择轻量主机、托管推理或单台 GPU 服务器，完成从 Feed/上传输入到衣橱、搭配、试穿、像素封面、购买清单和 Playground trace 的现场评审闭环。这个 Issue 不得反向阻塞 Issue 1–5。

### Acceptance criteria

- [ ] 使用最终 provider 组合记录显存、内存和时延，再确定部署规格；48 GB GPU、16 vCPU、64 GB RAM、300–500 GB NVMe 是重模型全自托管的安全上限建议，不是预先采购要求。
- [ ] 从干净 Ubuntu 22.04 主机可通过一套文档化命令启动最终 Compose；若采用托管推理或轻量 provider，同一领域 API 与任务状态保持不变。
- [ ] Nginx/H5、FastAPI、PostgreSQL/pgvector、Redis/Celery 和所选视觉/试穿 provider 健康运行；媒体使用 COS，公网只开放必要入口。
- [ ] 自托管重任务启用时由 Celery 串行调度，不因显存竞争破坏 API 可用性。
- [ ] 使用至少一条真实 Feed 视频和一组真实上传衣物完成整条 Demo narrative，保存 trace、模型版本、产物和时延证据。
- [ ] 前端通过移动 E2E、关键截图视觉验收、慢网与失败恢复；Feed 和 StyleCapture 两个视觉域协调且无 CSS/状态污染。
- [ ] Runtime 配置审计确认不存在 mock/stub、固定结果或提示词键控缓存；真实缓存可追溯到首次运行。
- [ ] 数据删除、私有媒体访问、密钥管理、数据库备份、日志脱敏和开源许可证检查通过。
- [ ] 独立验证没有未解决 P0/P1；验收范围内的问题必须在本 Issue 修复，不能转为新的“上线后优化”票。

### Blocked by

- [#2](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/2)
- [#3](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/3)
- [#4](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/4)
- [#5](https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/5)

开始本 Issue 时再准备部署目标、域名/COS 与所选 provider 凭据；这些不是前五个开发 Issue 的 blocker。

### User stories covered

81–96，以及前五条 Issue 的完整集成验收。
