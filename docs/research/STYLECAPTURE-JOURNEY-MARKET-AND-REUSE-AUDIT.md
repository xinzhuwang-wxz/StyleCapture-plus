# StyleCapture Journey 商业化调研与复用审计

- 日期：2026-07-27
- 市场：China-first，先上 iPhone App Store
- 工作名：StyleCapture Journey（中文工作名：衣程）
- 结论状态：可进入付费问题验证；未达到直接大规模开发或投放的证据门槛

## 1. 商业结论

StyleCapture 不应把原抖音 Feed 做成独立 App，也不应与现有“AI 衣橱”竞品比拼功能数量。首个可付费产品应聚焦一个有期限、有损失厌恶、结果可验证的任务：

> 在 3–7 天旅行前，用用户已有衣物生成按日/活动可执行的穿搭、备选与去重打包清单，让用户少带、少买错、途中少临时决策。

像素人物与世界观保留，但定位为完成计划后的成长、纪念与分享层。它不占首屏、付费墙主标题或 App Store 前三张截图，也不替代计划质量。

## 2. 首批用户与 JTBD

首要 ICP：23–36 岁、一二线与强旅游城市的 iPhone 女性；未来 30 天内有一次真实 3–7 天旅行且每年至少旅行三次；会在小红书、抖音、淘宝保存灵感；愿意导入至少 8 件覆盖必要槽位、推荐 12–30 件的本次衣物，但不会先完成整个衣橱数字化。

核心 JTBD：

> 当我要进行一次 3–7 天旅行时，结合逐日活动、天气、礼仪、步行强度、行李限制和已有衣服，告诉我每天穿什么、备什么、缺什么；当条件变化时，只重排受影响部分。

不首发服务：专业造型师、家庭衣橱、男性泛衣橱、二手卖家、穿搭博主生产工具、精确量体或 3D 数字人用户。

## 3. 市场证据与边界

| 证据 | 观察 | 对产品的约束 |
|---|---|---|
| [CNNIC 第 56 次报告](https://cnnic.cn/NMediaFile/2025/0730/MAIN1753846666507QEK67ZS9DH.pdf) | 短视频与网购已是高覆盖基础设施 | 平台擅长种草成交，独立 App 必须解决长期资产与决策，而非复制 Feed |
| [Acloset 中国区](https://apps.apple.com/cn/app/acloset-%E7%A9%BF%E6%90%AD-%E9%A3%8E%E6%A0%BC-%E6%97%B6%E5%B0%9A-%E4%BA%8C%E6%89%8B%E4%BA%A4%E6%98%93-%E6%9C%8D%E9%A5%B0%E6%95%B4%E7%90%86/id1542311809) | 免费容量大、订阅成熟，评论同时反映上传慢和泛推荐价值不足 | 不靠容量墙收费；首次价值必须在 5–10 分钟内出现 |
| [Whering 中国区](https://apps.apple.com/cn/app/whering-your-digital-wardrobe/id1519461680) | 旅行、周末与活动规划被持续强化，并有 credits 产品 | 场景包与订阅并存有合理先例 |
| [Indyx 中国区](https://apps.apple.com/cn/app/indyx-wardrobe-outfit-app/id1599179405) | 提供旅行穿搭与打包清单，但价格高且本地化弱 | 高端价格是上界，不是中国首发锚点 |
| [Stylebook 中国区](https://apps.apple.com/cn/app/stylebook/id335709058) | 一次买断，衣橱、日历和旅行打包是成熟能力 | 用户理解该问题，但对纯订阅存在阻力 |
| [爱搭衣橱](https://apps.apple.com/cn/app/%E7%88%B1%E6%90%AD%E8%A1%A3%E6%A9%B1-%E7%94%B5%E5%AD%90%E8%A1%A3%E6%A9%B1-ai%E6%90%AD%E9%85%8D-ai%E8%AF%95%E8%A1%A3/id6747186089) | 本地产品已覆盖天气、场合、批量入库与 AI 试衣 | “泛 AI 搭配”不是差异化，执行计划和可信恢复才是 |
| [Apple Product Page Optimization](https://developer.apple.com/help/app-store-connect-analytics/acquisition/product-page-optimization/) | 可测试图标、截图、预览与描述，并给出置信度 | 获客实验直接使用 Apple 成熟能力，不自建商店页实验系统 |
| [Apple Custom Product Pages](https://developer.apple.com/help/app-store-connect/create-custom-product-pages/configure-multiple-product-page-versions/) | 最多可创建 70 个场景化页面并独立看转化 | 先为城市旅行、天气变化、轻装行李等旅行意图建立入口；单日场合以后独立验证 |

这些证据证明问题与竞品类别存在，但不证明 StyleCapture 已达到 PMF。P0 只用同质的 3–7 天旅行 cohort 验证，避免把旅行、婚礼、面试和约会的需求强度与购买率混成无意义均值。

## 4. 付费假设

首发 SKU：

- 免费：至少 8 件覆盖必要槽位、最多 30 件本次衣物；旅行 Day 1 完整主 Look；旧计划永久可看；基础像素角色。
- 单次旅行包：统一 ¥12；解锁 Day 2–7、全部备选、跨日去重打包与缺口清单、3 次 AI 重排、14 天天气刷新，并支持跨设备 entitlement 恢复和永久只读查看。
- Pro：可先完成 StoreKit/服务端技术配置，但不作为 M0/M1 默认 CTA；只有 60 天第二个独立付费 Journey 达到 25% 后才允许主推月订阅，年订阅只在第二次付费 Journey 后展示。权益限于完整衣橱同步、持续编辑、跨 Journey 偏好和像素档案，不得锁住已购旅行包。
- 真人试穿不进入首发权益；未来若质量与毛利达标，按结果包单独售卖，失败自动返还。

单位经济按 Apple 中国大陆 2026-03-15 起的费率做双情景，不预设一定获批 Small Business Program。Apple 公布中国大陆标准佣金为 25%，符合该计划的开发者为 12%：[Apple 中国大陆业务调整](https://developer.apple.com/cn/news/?id=dadukodv)。未计税与退款前：

| SKU | 标价 | 12% 佣金后 | 25% 佣金后 | 允许的天气/模型/存储成本（净收入 25%） |
|---|---:|---:|---:|---:|
| Journey pack | ¥12 | ¥10.56 | ¥9.00 | ¥2.64 / ¥2.25 |
| Pro 月订阅 | ¥18 | ¥15.84 | ¥13.50 | ¥3.96 / ¥3.38 |
| Pro 年订阅 | ¥128 | ¥112.64 | ¥96.00 | ¥28.16 / ¥24.00 |

每次生成前按 entitlement 预留预算；失败释放，成功才结算。定价实验同时报告标价转化、Apple 佣金情景、退款、实际 provider 成本和贡献毛利，禁止只看流水。

第一次付费墙先展示 Day 1 完整主 Look，再准确列出可解锁的 Day 2–7、全部备选、跨日去重打包、缺口和天气修订。M0/M1 只有一个 take-it-or-leave-it ¥12 旅行包 offer，不做 ¥8/¥12/¥18 选择题。禁止在注册或上传前硬墙，禁止锁住用户自己的衣物和已购买旧计划。

## 5. 仓库内直接复用

| 能力 | 现有实现 | 决定 | 理由与限制 |
|---|---|---|---|
| Wardrobe Item/Look 事实 | `services/backend/src/stylecapture_backend/features/wardrobe/`、`features/look/` | 直接复用领域语义，适配 iOS API | Item 保持衣物事实真源；Trip 只引用，禁止复制衣物字段 |
| 场景搭配 | `features/outfit/domain.py`、`features/outfit/application.py` | 直接复用确定性约束与 LiteLLM rerank，扩展为 Trip orchestrator | 当前请求只覆盖单场景，不包含多日、复穿、行李与天气快照 |
| 图片入库/异步识别 | `features/capture/`、Celery Worker | 适配复用 | 排除 Feed 专属 frame/lasso 入口；保留 upload、ownership、job、retry、delete |
| RenderArtifact | `features/render/`、`features/item_presentation/`、`features/pixel_trial/` | 直接复用派生物、hash、状态与降级语义 | 首发只启用真实单品拼贴与轻量像素纪念；真人试穿默认关闭 |
| 认证与上传隔离 | `platform/session.py`、ADR 0002 | 复用安全约束，替换传输形态 | 浏览器 cookie 改为 iOS access/refresh token；资源所有权与删除语义不变 |
| 模型网关与成本保护 | LiteLLM adapters、`platform/cost_guard.py` | 直接复用并增加套餐预算 | 应用层继续只认 capability alias；补 token/spend 和 entitlement guard |
| OpenAPI 真源 | FastAPI OpenAPI、`scripts/export_openapi.py` | 直接复用 | iOS 使用 Apple Swift OpenAPI Generator，不手写 DTO/client |
| Pixel 世界视觉 | `apps/h5/src/features/community/`、`public/assets/community/` | 适配复用视觉资产与模拟规则 | 不迁移 H5 社区/舞会主循环；只做旅程邮戳、明信片、角色衣装 |
| H5 Feed | `apps/h5/src/features/feed/` | 拒绝进入独立 App | 既不是付费结果，也会抬高内容版权、审核和运营成本 |
| H5 交互代码 | React/Vite 页面、localStorage | 不跨端复制 | 仅把用户旅程、色彩与像素资产当参考；iOS 使用原生 SwiftUI |
| 现有 scene/collage Skills | `skills/scene-outfit-matching`、`skills/real-photo-flat-lay-collage` | 仅保留 legacy/support facade | 边界正确但只覆盖单场景/渲染，不能证明 Trip、Packing、entitlement、deletion 或生产 AI |
| 现有 Doubao Skill | `skills/doubao-virtual-try-on`、ADR 0006 | Journey runtime/evidence 禁用 | 直接绑定 provider/key/prompt/local photo，是独立 Codex 工具，不具备产品账号、同意、权益、成本、删除和观测边界 |

## 6. 外部开源与平台复用

正式接入前，在每个 Issue 的 ExecPlan 重新核对当前 release、commit、许可证与 privacy manifest。

| 能力 | 项目/平台 | 当前核对版本或 commit | 许可证 | 决定 |
|---|---|---|---|---|
| 原生 UI/状态/并发 | SwiftUI、Observation、Swift Concurrency | 随目标 Xcode/iOS SDK | Apple SDK | 直接使用 |
| 原生认证/密钥/网络/通知 | AuthenticationServices、Security/Keychain、Network、UserNotifications | 随目标 iOS SDK | Apple SDK | 直接使用 credential revocation、设备内密钥、网络变化与本地通知；不引入 reachability/keychain wrapper/推送 SDK |
| 图片格式与降采样 | CoreTransferable、UniformTypeIdentifiers、ImageIO | 随目标 iOS SDK | Apple SDK | 直接使用 HEIC/类型协商/metadata stripping/downsample，不手写解析器 |
| 行程截图 OCR | Apple Vision `VNRecognizeTextRequest` | 随目标 iOS SDK | Apple SDK | 设备端直接使用；原图默认不上云，文本必须由用户确认后才写 Occasion |
| 天气 | Apple WeatherKit / WeatherKit REST | 随 Apple Developer entitlement | Apple service | 首选候选；实施前以中国目标城市覆盖、归因、配额、服务端签名和降级 smoke 决定 direct/adapt，禁止自写天气预测 |
| Xcode 工程生成 | [yonaskolb/XcodeGen](https://github.com/yonaskolb/XcodeGen) | `2.46.0` / `8445e77` | MIT | 使用可审查的 `project.yml` 生成 `.xcodeproj`，不手工维护工程文件；规模达到多模块缓存/选择性测试瓶颈时再评估 Tuist |
| API client 生成 | [apple/swift-openapi-generator](https://github.com/apple/swift-openapi-generator) + runtime + URLSession transport | generator `1.13.0` / `af9a2a1`; runtime `7c9f2b6`; URLSession `08796d3` | Apache-2.0 | 直接使用，构建时生成，不提交生成源码 |
| 离线数据库与 outbox | [GRDB.swift](https://github.com/groue/GRDB.swift) | `v7.11.1` / `b83108d` | MIT | 使用；比为同步/迁移需求强行套 SwiftData 更可控 |
| 图片加载/缓存 | [Nuke](https://github.com/kean/Nuke) | `13.0.6` / `63a8fcb` | MIT | 使用；不手写 downloader/cache |
| IAP 服务端 | [apple/app-store-server-library-python](https://github.com/apple/app-store-server-library-python) | `v3.1.2` / `4eaa224`，HEAD `200e9ac` | MIT | 使用 StoreKit 2 + Apple 官方服务端库与 Notifications V2 |
| Paywall UI | StoreKit `ProductView` / `SubscriptionStoreView` 与自定义 SwiftUI | 随目标 iOS SDK | Apple SDK | Task 7 先做本地化/可访问性对照；系统 view 能满足上下文 pack-first 体验则直接使用，否则仅保留必要自定义布局 |
| Apple identity token | PyJWT `[crypto]` + Apple JWKS/REST | 实施时重验稳定版 | MIT | 候选直接复用 JWT/JWK/签名原语；应用层只依赖 AppleIdentityVerifier，禁止自写 JOSE |
| COS/S3 client | AWS boto3 S3 client + COS S3-compatible endpoint | 实施时重验稳定版 | Apache-2.0 | 候选适配复用；若 COS 兼容性 smoke 不满足 checksum/lifecycle/SSE/signing，再比较腾讯 COS 官方 SDK |
| 托管订阅平台 | [RevenueCat purchases-ios](https://github.com/RevenueCat/purchases-ios) | HEAD `a268c9b` | SDK MIT，服务另行计费 | P0 拒绝；China-first 数据跨境、供应商成本与现有 Python 后端使官方链路更合适；全球化时重评 |
| 产品分析 | [sensorsdata/sa-sdk-ios](https://github.com/sensorsdata/sa-sdk-ios) | `v5.0.10` / `b71f54a` | 商用需购买许可 | 不作为默认免费依赖；若采购通过再以 AnalyticsPort 适配，首发先用最小化一方事件 + App Store Connect |
| AI 网关/路由/预算 | [LiteLLM](https://github.com/BerriAI/litellm) | 仓库锁定 `>=1.60,<2` | MIT | 直接复用现有 Proxy、capability alias、fallback、rate limit 和 spend tracking；禁止业务模块直接调用 provider SDK |
| AI 工作队列 | [Celery](https://github.com/celery/celery) + Redis | 仓库锁定 `>=5.4,<6` | BSD-3-Clause | 直接复用，任务必须幂等并与 DB outbox/inbox 配合；只有多日工作流恢复成为实测瓶颈时才评估 Temporal |
| 向量召回 | [pgvector](https://github.com/pgvector/pgvector) | 容器固定 pg17 digest，Python `>=0.3,<1` | PostgreSQL | 直接复用；先 SQL + exact/现有索引，达到技术设计阈值后使用 HNSW，不提前引入独立向量数据库 |
| LLM 评测/红队 | [promptfoo](https://github.com/promptfoo/promptfoo) | 仓库固定 `0.121.19` | MIT | 扩展现有 Product API eval；在 CI 做结构化质量、回归、prompt injection 与越权红队，不自建评测 runner |
| AI 追踪与数据集 | [Langfuse](https://github.com/langfuse/langfuse) + OpenTelemetry | 审计 `v3.185.0` / `5d12dc3`；实施时按自托管兼容矩阵重验 | core MIT，`ee/` 除外 | 软启动前通过 edition/control gate 后在境内部署；OSS 只有在外部控制补齐 retention/audit/RBAC/delete 时可用，否则采购合适版本或阻断。拒绝捕获 prompt/completion 的默认 callback，只接 metadata-only 双 allowlist OTLP |
| 标准遥测 | OpenTelemetry Python SDK、FastAPI/Celery instrumentation、OTLP exporter/Collector | 实施时按兼容矩阵固定 | Apache-2.0 | 直接使用标准 instrumentation/export；不自写 trace protocol 或 exporter |
| 基础设施即代码 | Terraform + TencentCloud provider | 实施时固定 provider/version/commit | MPL-2.0 | Stage B 直接使用；先做 plan/security review，不手写云资源脚本 |
| 业务 AI 编排 | LangChain/LlamaIndex/PydanticAI/自建 agent framework | 现阶段无 agent/RAG 工具调用需求 | 各异 | P0 拒绝新增；Trip 是确定性领域编排 + 一次封闭候选 rerank，加入通用 agent 框架只会复制已有 application/Celery/LiteLLM 边界 |
| Native shortcut | Apple App Intents / App Shortcuts | 随目标 SDK | Apple SDK | 付费核心验证后可直接复用；只调用 app service/generated client，不建第二规划器 |
| Future agent gateway | 官方 MCP SDK或 OpenAPI tool exposure | 需求成立时重验 | 实施时审计 | P0 不发布；先有 mature delegated auth/consent/revocation/entitlement/deletion，再选成熟协议，不写 ad-hoc Skill server |
| 非商业试穿 | FastFit `9c96fc0` | 仓库既有审计 | Non-Commercial | 商业运行时禁止；除非获得书面商业授权 |

## 7. 7/30/90 天决策门

| 时间 | 样本与交付 | 通过条件 |
|---|---|---|
| M0（7 天招募/报价 + 旅行后成熟；达到成熟分母后决策） | 20–30 名未来 30 天有真实 3–7 天旅行的 ICP；至少 15 人收到完整 concierge 计划；所有人只收到同一个 ¥12 offer | pain denominator ≥20 且 ≥60%；real-paid denominator 为全部 offer recipients、≥15，rate ≥33% 且 payer ≥5；execution denominator 为 `trip_end+7d` 已成熟的全部 recipients、≥15，rate ≥50%，未回访按未执行；记录实际 maturity cutoff。`real_paid` 不接受意愿、口头或等价承诺 |
| Day 30 技术门 | TestFlight 150–300 名目标用户；≥100 个 preview eligible | 只判断 activation、preview completion、P50/P90 首次价值、plan quality/lock、restore 与技术购买；sandbox/TestFlight 交易不得计入 WTP、生产转化、收入、退款或毛利 |
| 生产初验 | 中国区生产版本至少 200 个 `eligible_paywall` 且至少 20 个首次真实付款 | 可声称初步付费验证并继续受控迭代；未满样本不得凭百分比扩投 |
| Day 90 扩量门 | 至少 500 个生产 `eligible_paywall`、50 个真实付款；另按指标冻结成熟 cohort | 首次付费转化 ≥8%；完整付费计划交付后锁定 ≥75%；`trip_end+7d` confirmed-worn denominator ≥30 且 VSS ≥55%；`first_purchase+60d` repeat denominator ≥50 且第二单已交付/未退款的 repeat ≥25%；首购满 30 天订单 denominator ≥50 且退款 <5%；毛利 ≥65% |

满足任一条件就 Kill 当前旅行楔子并停止扩量：两轮各至少 100 个生产 `eligible_paywall` 且质量门通过后，合并首次付费转化仍 <3%；至少 50 个成熟付费锁定 Journey 的 confirmed-worn VSS <30%；至少 100 个付费 Journey 且完成一次成本优化后毛利仍 <40%；或至少 20 个流失访谈中 ≥60% 的首要原因是“结果没有货币价值”。Iterate 使用不重叠半开区间：`3% ≤ conversion <8%`、`30% ≤ confirmed VSS <55%`、`10% ≤ 60d repeat <25%`、`40% ≤ gross margin <65%`。Kill 的是旅行楔子，不是现有衣橱资产层。

指标公式、排除项与事件字段以 `docs/product/STYLECAPTURE-JOURNEY-PRD.md` 第 4–5 节为唯一真源。App Store Product Page Optimization 只优化达到生产 paid VSS 的获客成本和质量，不能用下载量替代付费结果。

## 8. M0 调研运营控制

仓库内 M0 运营面位于 `docs/research/journey-validation/`，只保存访谈脚本、concierge 模板、决策日志、脱敏指标 schema、原始材料 `.gitignore` 与可复算校验命令；真实联系方式、照片、录音、转写、支付截图、退款记录和导出文件不得进入 Git。

为保留至少 15 名达到 `trip_end+7d` 的成熟 plan recipients，实际招募目标按 30 人执行，而不是用刚好 20 人作为运营目标。渠道构成单独报告并执行上限：自然搜索/公开意图发现 ≤50%，经批准的女性/旅行群 ≤35%，二度转介绍 ≤25%，职业创作者 ≤20%。禁止转介绍赏金、按量付费群主、信息流广告、正反馈奖励和完成现金奖励；需要补偿研究劳动时，只能使用与正反馈、付款或执行结果无关的固定劳务费。

资格确认必须包含：7-30 天内确认出发、3-7 天过夜旅行、至少 8 件本次自有衣物且推荐 12-30 件、低敏证明可出示并在姓名/订单/证件/精确住宿/联系方式打码后删除。团队成员、直系亲属、历史 pro 试用者、重复主体、非目标行程和无法提供证明者排除；旅行取消者退款并记录，不用另一个场景替换。

所有 complete-plan recipients 只收到一个完全相同的 ¥12 可退款订金 offer，权益与退款条款一致。支付和退款原始证据与研究指标分离保存，不使用个人收款码，不作为 iOS 外部付款链接，也不计入 App Store 产品权益。`real_paid` 只接受真实支付或可退款订金；意愿、口头承诺、等价承诺、创作者置换和群主渠道准入都不计入 numerator。

复算路径复用仓库已锁定的 Python `jsonschema` 运行时：

```bash
uv run python scripts/journey_validation_metrics.py validate path/to/m0-aggregate.json
```

该命令校验 `docs/research/journey-validation/metrics.schema.json`、扫描明显联系方式、拒绝单日/非旅行 cohort、强制唯一 CNY 12 offer，并重新计算 `pain_rate`、`real_paid_rate`、`execution_rate` 与实际 maturity cutoff。当前仓库尚无真实 cohort、支付或成熟后执行证据，因此不得记录 `GO` 或启动 Task 2。
