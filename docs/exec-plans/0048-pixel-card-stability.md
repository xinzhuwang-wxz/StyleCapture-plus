# Issue #48：像素小人卡片画风稳定性

**Issue:** https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/48
**Branch:** `feat/issue-48-pixel-card-stability`

## 目标

让照片转像素和 Look 像素封面共享一套可追踪的竖版 3:4 角色卡合同：固定粗颗粒像素画风与人物完整性，同时根据服装颜色、款式和气质自适应卡片背景，不再机械套用粉紫蝴蝶结模板，也不退化成纯色空背景或复杂写实场景。

## 用户可见结果

- 单人全身角色完整呈现，头顶、鞋底和四周有留白，脚下有轻量椭圆地毯。
- 发型、眼镜、表情、服装版型、主色、鞋履和关键配饰来自输入图；半身输入只补全不可见下装与鞋履。
- 像素块清晰、颗粒偏粗、边缘阶梯化，不是细腻写实插画或平滑矢量图。
- 背景移除原图复杂场景，用服装主色/辅色和气质决定甜美、淡雅、清爽或酷感卡片；包含少量轻量主题图标与点状装饰，但不喧宾夺主。

## 范围

1. 把用户授权的两组正面案例纳入仓库：像素输出作为运行时风格锚点，原图与输出配对用于评测说明。
2. 新增可独立调用照片转像素 Product API 的 `pixel-character-card` Skill；Skill 不复制运行时 Prompt、不直连模型、不持有密钥。
3. 精简并版本化 `photo.pixel_trial` 与 `look.pixel_cover` 中文 Prompt，明确内容图与最后两张风格图的职责。
4. 在两个像素人物生成路径中固定追加风格锚点，并只在像素人物调用中使用稳定生成参数。
5. 增加 Skill、Prompt、参考图顺序、3:4 尺寸与 provider payload 的合同测试。
6. 单并发运行真实 Seedream 对照验证，保存耗时、参数和视觉结论；不把私密原图或密钥写入仓库、日志或 trace。

## 非目标

- 不修改单品方形像素图能力。
- 不重做小程序整体 UI。
- 不承诺所有输入一次生成必然完美，也不默认并发生成多张图。
- 不引入本地重量级生图模型或第二个模型网关。

## 复用审计

| 能力 | 候选 | 决策 | 原因 | 来源/许可证 |
|---|---|---|---|---|
| 照片上传、异步任务与结果下载 | 现有 `/v1/uploads`、`/v1/pixel-trials` 与 H5 `createPixelTrial` | 适配复用 | 保持 H5、Skill 与外部调用方使用同一 Product API，不复制业务状态机 | 本仓库 `784f2cc`；项目内代码 |
| 生图路由 | 现有 `LiteLLMImageGenerator` 与 `image_generation` 能力别名 | 适配复用 | 继续隐藏 Seedream 模型 ID、鉴权和 provider payload | 本仓库 `784f2cc`；项目内代码 |
| Skill 脚本结构 | `scene-outfit-matching` API facade；`doubao-virtual-try-on` 的结果审计思路 | 适配前者，拒绝后者直连 Ark 的方式 | ADR-0005 要求产品 Skill 调用 Product API；本能力已有完整 API | 本仓库 `784f2cc`；项目内代码 |
| 画风锚点 | 用户授权的两组正面案例 | 直接复用 | 图像比继续增加形容词更能固定脸部比例、像素颗粒和卡片结构 | 用户提供并明确授权提交；仅本项目参考用途 |
| 负面案例 | 用户提供的两组失败图 | 仅用于规则与人工验收，不作为运行时参考 | 向生成模型输入失败图会增加错误模板污染风险，且未获得明确的仓库存储授权 | 用户会话内评测素材，不提交 |
| Prompt 评测 | 现有 pytest provider/processor tests 与 Promptfoo Product API 路径 | 适配复用 | 覆盖生产同款网关、任务状态与 trace，无需新评测框架 | 本仓库 `784f2cc`；项目内代码 |

## 实施步骤

1. 复制并记录两组获授权正面案例，补齐来源与用途说明。
2. 先添加失败的合同测试：参考图顺序、短 Prompt、背景自适应规则、稳定参数与 Skill API facade。
3. 实现共享风格锚点加载器，接入照片转像素与 Look 像素封面，不影响真人试穿和单品像素图。
4. 用结构化、短小的中文 Prompt 替换长串正反描述并升级版本。
5. 用 `skill-creator` 初始化并实现 `pixel-character-card` Skill，生成匹配的 `agents/openai.yaml`。
6. 运行 Skill 校验、目标 pytest、ruff/mypy、前端类型检查与 Promptfoo smoke。
7. 在资源检查通过后，串行运行真实 Seedream 正/反输入对照并形成视觉结论；必要时只调整一次 Prompt/参数。
8. 更新 Capability 目录、Issue 与本计划，提交小范围 PR。

## 进度

- [x] 同步远端最新 `main`，创建 Issue #48 和独立分支。
- [x] 阅读产品、架构、Provider 与 Skill 治理真源。
- [x] 确认两组正面案例可提交，反面案例只用于评测。
- [x] 纳入正面案例与来源说明。
- [x] 完成失败合同测试和实现。
- [x] 完成 Skill 校验和目标离线合同测试。
- [x] 完成全量离线验证（GitHub Linux product-ci 已通过 Python、API 合同、移动端与 Compose/backend image 全部检查）。
- [ ] 完成真实 Seedream 对照与视觉审查。
- [x] 更新 GitHub 证据并打开 PR #49。

## 决策记录

- 2026-08-08：以“固定画风骨架 + 自适应背景主题”替代单一粉紫卡片模板。人物与像素风是低自由度；背景色和图标语义是受约束的中自由度。
- 2026-08-08：运行时只输入正面风格锚点；反面案例转化为禁区和质量门槛，不输入 Seedream。
- 2026-08-08：Skill 使用中文正文并调用 Product API；Provider Prompt 仍在 feature 内就近维护，遵守 ADR-0005。

## 意外与发现

- 现有 Prompt 虽不算超过模型 token 限制，但把画幅、人物保真、像素技术、背景策略和大量否定词平铺在同一段中；同时未发送任何正面画风参考图，导致 Seedream 只能靠文本猜测风格。
- 现有图片 Provider 只发送尺寸与图像，没有固定 seed 或 guidance 参数；成功判定只验证文件有效，没有美学质量门槛。
- 在线 Product API 仍运行 `main`，不能代表本分支的新 Prompt 与锚点；将获授权仓库参考照上传线上服务还需要用户对该具体外发目的地的明确同意。因此本地只完成无网络链路与合同验证，真实 Seedream 视觉样例保留为部署后验收项。
