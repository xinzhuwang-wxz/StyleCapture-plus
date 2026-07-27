# StyleCapture Journey Goal and Review Controls

- Status: ready after planning review
- Branch: `codex/stylecapture-journey`
- Worktree: `/Users/bamboo/Githubs/StyleCapture-plus-commercial-app`
- Goal must not be started from `main`.

## Aggregate Goal launch prompt

Paste the following into the Codex task after the reviewed planning commit is present on the branch:

```text
在 /Users/bamboo/Githubs/StyleCapture-plus-commercial-app 的 codex/stylecapture-journey 长期分支上，自主管理并交付 StyleCapture Journey（衣程）独立付费 iPhone App。先读取 AGENTS.md、plan.md、docs/product/STYLECAPTURE-JOURNEY-PRD.md、docs/architecture/STYLECAPTURE-JOURNEY-TECHNICAL-DESIGN.md、docs/architecture/JOURNEY-SKILL-CAPABILITY-REGISTRY.md、docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md、docs/adr/0007-native-ios-trip-planning-and-storekit.md、docs/exec-plans/0043-stylecapture-journey-commercial-app.md、docs/superpowers/plans/2026-07-27-stylecapture-journey.md、docs/engineering/AUTONOMOUS-DEVELOPMENT-LOOP.md 和 docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md，并将本段设为唯一 aggregate Goal；plan.md 中标为 Legacy demo route 的旧 Feed/H5 内容仅是历史参考，不是 Journey 指令；下层 SDD task brief、ExecPlan 或实现与本 Goal 冲突时，修正下层真源。

终端结果：以中国大陆 App Store 为首发市场，交付一个 iOS 17+ 原生 SwiftUI App。用户针对真实 3–7 天旅行，只选择至少 8 件覆盖必要槽位、推荐 12–30 件的已有衣物，即可得到按日/活动的主穿搭、条件备选、局部替换、天气修订、跨日去重打包与缺口清单；Day 1 主 Look 免费，通过 StoreKit 2 以 ¥12 解锁 Day 2–7、全部备选、打包、缺口和天气修订，能跨设备恢复、退款/撤销、离线使用并完成账户级删除；计划执行后获得去敏像素旅程纪念。Feed、婚礼/面试/约会等单日场合、泛 AI 聊天、社交社区、P0 真人试穿、3D 和 Android 不在本 Goal。

严格执行先验证后开发：M0 在 7 天内完成招募和统一 ¥12 报价，最终门只在至少 15 名 plan recipients 达到 `trip_end+7d` 后判断，并记录实际 maturity cutoff。招募 20–30 名未来 30 天有真实 3–7 天旅行的 ICP；pain denominator ≥20 且 ≥60% 评分 ≥7/10；全部收到完整计划和唯一 offer 的用户构成 real-paid denominator（≥15），真实可退款付款/订金 rate ≥33% 且 payer ≥5；`trip_end+7d` 已成熟的全部 plan recipients 构成 execution denominator（≥15），≥50% 至少一天采用计划主/备选 Look 或符合原硬约束的可追踪局部替换，未回访按未执行。三项同时通过才进入完整原生 P0；`real_paid` 不接受意愿、口头或“等价”承诺，研究收款不得变成 iOS App 外链支付。未通过则记录 PIVOT/STOP，不得用增加场景或功能绕过需求证据。之后按 ExecPlan 的 M1–M7 和 Implementation Plan 的 Task 2–10 依赖顺序创建/执行 branch-local milestone ExecPlans 和 SDD task briefs，持续推进，不在里程碑之间等待人工确认。除非未来得到明确授权，不得读取、创建、编辑、评论、关闭或以其他方式触碰 GitHub Issues 或 PRs。

成熟框架优先是硬门禁。iOS 采用 TCA `1.26.1` exact pin（`ead11e04e5011c437722c1990d22f80d87056978`）作为 production app shell，使用当前 non-deprecated APIs，并在 M2 前做 2.0 migration/deprecation audit；TCA owns feature composition、state、dependency clients、effects/cancellation、navigation/state restoration 和 TestStore，SwiftUI/Observation/Swift Concurrency/NavigationStack 负责渲染、生命周期和系统集成。不得自建 AppRouter、全局 AppEnvironment、ViewModel app shell、DI container、effect runner 或 navigation framework。iOS 继续优先 Apple 官方框架（Sign in with Apple、PhotosPicker、StoreKit 2、BackgroundTasks、OSLog、MetricKit、Swift Testing、XCTest/XCUITest、Xcode Cloud/TestFlight），用 XcodeGen 生成工程，用 GRDB 管离线投影/outbox，用 Apple Swift OpenAPI Generator 生成客户端，用 Nuke 管图片；不得手写这些基础设施。所有 BackgroundTasks identifier 必须进入 `BGTaskSchedulerPermittedIdentifiers` 并实测 expiration/denied/relaunch。后端复用现有 FastAPI 模块化单体、PostgreSQL/pgvector、Redis/Celery、COS/S3、LiteLLM；AI 生产栈使用 LiteLLM Proxy 做唯一网关/路由/实际 token-spend，Celery + PostgreSQL transactional outbox/inbox 做幂等任务，pgvector 做 owned-item 检索，Promptfoo 分 branch smoke、AI quality-gate、release redteam，OpenTelemetry 做标准遥测，并在软启动前部署通过 edition/control gate 的境内 Langfuse。不得启用捕获 prompt/completion 的默认 LiteLLM callback；应用 metadata allowlist 与 Collector 第二 allowlist 都通过才可发送，sanitizer 失败时 telemetry fail-closed。Langfuse 必须私网/TLS、关闭公开注册/邮箱密码/部署 telemetry、启用 SSO+MFA、隔离 project/key 并证明 RBAC/audit/retention/export/delete；OSS 外部控制补不齐时采购合适版本，否则阻断发布。Promptfoo 仅用合成/授权脱敏数据在临时隔离 CI 运行，关闭 telemetry/sharing/remote generation/cache，并用 privacy canary 验证 Langfuse、Collector、Prometheus、Promptfoo 与 CI artifact 零泄漏及删除传播。Commerce UsageReservation 是套餐权益/次数真源，LiteLLM 是模型用量/成本真源，RedisCostGuard 只做实时并发/速率/滥用熔断。Skill 不是智能架构：现有单场景/拼贴 Skill 只是 legacy/support facade，直连豆包的 standalone Skill 严禁进入 Journey runtime、China P0 和发布证据。P0 不发布可下载 Agent Skill；未来 Apple App Intents 或 external Skill/MCP 只能通过生成合同调用同一 Product API/application use case，先通过 delegated auth、同意、撤销、权益、成本、删除和安全门。不要新增第二套 provider client、工作流引擎、向量库、LLM dashboard、eval runner、API DTO 或通用 agent framework；只有现有成熟能力经过复用审计确实不满足可测需求时，才用 ADR 和基准证据引入替代。

每个 branch-local milestone task 必须交付从 iOS UI、generated API、domain/application、persistence、worker/provider 到真实失败恢复的完整 vertical slice。先写一个失败的公开行为测试，再做最小实现；每次 API/schema 变化立即做 migration up/down、OpenAPI diff 和 Swift client compile。新依赖、SDK、权限、provider、数据接收者、基础算法或合同实现前，必须记录 capability -> candidates inspected -> direct/adapt/reject -> reason -> exact source commit/release/license；遗漏复用审计、重复造轮子、复制未使用子系统、手写可生成合同或引入大依赖是 P1 阻断。

把安全、隐私与合规当发布功能：SIWA 在服务端验证 issuer/audience/nonce/signature/time/replay，使用可撤销短 access + rotating refresh session；StoreKit entitlement 只认 Apple 已验证交易和服务端 ledger；P0 禁用境外真人照片处理和非商业 FastFit；照片只进受保护私有目录，对象存储私有且可审计删除；账户删除撤销会话、阻断旧任务复活并覆盖 DB、对象、派生物、embedding、prompt、cache、processor 与 backup SLA；AI 图片预览/下载/分享保留显式和隐式标识；完成 APP 备案、适用的生成式 AI 备案/登记、18+、PrivacyInfo.xcprivacy、App Privacy、DPA/processor register 和网络流量核对。任何 P0/P1 合规或跨账户问题不得推迟到上线后。

实行双触发审查。事件触发：每逢 public API/schema、新依赖/SDK/provider/permission/data recipient、账户/StoreKit/删除/上传/成本/AI 标识变化、首次端到端可见旅程、加入 fallback、放宽测试、出现重复/生成代码、或某里程碑首次声称完成，立即暂停扩展，运行里程碑质量门。时间触发：活跃开发每小时在同一任务/工作区审计 Goal、ExecPlan、当前 SDD task brief、diff、测试、trace、截图和资源；它只做 steering，不开第二条实现分支，且不得触碰 GitHub Issues 或 PRs，除非未来得到明确授权。发现偏航、冗余、抽象过度、provider 泄漏、隐私字段、隐藏 mock、成本失控或缺失失败态时，安全范围内立即修复并重验；必要时修订当前 SDD task brief/ExecPlan，跨切面持久决策才写 ADR，不能用 branch-local follow-up 隐藏当前验收失败。

每个里程碑都必须获得新鲜证据：domain/property tests；migration/OpenAPI/generated client；PostgreSQL/Redis/Celery/COS integration；Promptfoo 质量与安全门；必要的真实天气/模型/Apple sandbox smoke；iOS 小/中/大屏、弱网/断网、后台恢复、低存储、权限拒绝、Dynamic Type、VoiceOver；initial/input/processing/success/failure/recovery/paywall/purchase/delete 的真机截图或录屏；独立 spec、reuse/license、architecture、security/privacy、code quality、conversion UX review。修复所有 P0/P1，做 changed-file 去冗余清理，再重复所有受影响验证。不可用 mock、固定结果或旧证据宣称完成，观察/评测系统故障不得阻断主链路。

自主管理 branch、commit、push、本地 review、TestFlight/staging 和部署；所有 commit 遵守 Lore protocol，不覆盖或回退他人工作。除非未来得到明确授权，不得读取、创建、编辑、评论、关闭或以其他方式触碰 GitHub Issues 或 PRs。生产或 App Store 的不可逆/凭据授权步骤若确需用户权限，先完成所有可替代的本地/staging 工作并只报告精确阻塞。遵守本机资源护栏，重 AI 使用托管 provider，长任务每五分钟检查资源并降低并发。

商业和规模 stop condition：严格使用 PRD 的冻结 cohort 和成熟分母；TestFlight/sandbox 只算技术证据，不计 WTP、生产转化、收入、退款或毛利。生产至少 200 个 eligible paywall/20 个付款才可称初步验证。以下任一 kill trigger 成立即停止扩量并 PIVOT/STOP：两轮各 ≥100 个生产 eligible paywall 且质量门通过后合并转化 <3%；≥50 个成熟付费锁定 Journey 的 confirmed-worn VSS <30%；≥100 个付费 Journey 且完成一次成本优化后毛利 <40%；≥20 个流失访谈中 ≥60% 首要原因是无货币价值。只有中国区可发布版本真实完成，且同一决策记录同时满足 ≥500 个生产 eligible paywall、≥50 个真实付款、首次付费转化 ≥8%、付费完整计划 delivered→lock ≥75%、PRD 最小成熟分母上的 confirmed-worn VSS ≥55%、60 天第二次付费 Journey ≥25%、毛利 ≥65%、退款 <5%，恢复/删除/对账/回滚及 AI observability privacy canary/删除传播通过，无 unresolved P0/P1，最终六类审查均 APPROVE + CLEAR，才可完成 Goal。订阅在 60 天复购门通过前不得作为默认 CTA，年订阅只在第二次付费后展示。若 M0 或后续 kill gate 失败，记录有证据的 PIVOT/STOP 并将 Goal 标记 blocked，等待新的产品方向授权，不要假装原 Goal 已完成。
```

## Hourly heartbeat automation prompt

Create one recurring hourly automation only after the Goal is active. It must target the same Codex task and worktree; do not create a second implementation task.

```text
审计同一 StyleCapture Journey Goal 的当前执行状态。读取 active Goal、docs/exec-plans/0043-stylecapture-journey-commercial-app.md、当前 milestone ExecPlan、当前 SDD task brief、相关 ADR、最近 diff/commit、测试、OpenAPI/generated client、Promptfoo/Langfuse/OTel 证据、iOS 截图/录屏和资源状态。不得读取、创建、编辑、评论、关闭或以其他方式触碰 GitHub Issues 或 PRs，除非未来得到明确授权。判断工作是否仍直接推进 3–7 天付费旅行结果；检查是否混入单日场合或订阅抢跑，遗漏验收、隐藏 mock/fixed result、测试放宽、手写可生成合同、重复框架/算法、无依据抽象/依赖、provider 直连、敏感 trace/event、跨账户/StoreKit/删除/AI 标识漂移、失败/恢复 UX、成本/毛利，以及 TestFlight 与 production denominator 是否分离。检查 CPU、memory pressure、swap、thermal、disk、Docker 和重复 watcher；触发护栏时降并发或停止昂贵本地任务。对安全且在当前 SDD task brief/ExecPlan 范围内的 P0/P1 立即修复并运行受影响验证；需要持久跨切面决策时更新 ADR，需要当前结果的发现直接修订 SDD task brief/ExecPlan，不创建逃避验收的 branch-local follow-up。然后继续当前 milestone。仅报告实质修正、精确阻塞或简洁 clean audit；Goal 完成、blocked 或分支暂停时禁用本 automation。
```

## Event-driven milestone review prompt

Use this prompt after every milestone and whenever an event trigger in the ExecPlan fires:

```text
对 StyleCapture Journey 当前 milestone 运行独立质量门。固定当前 Goal、branch-local acceptance criteria 和 git diff；不得触碰 GitHub Issues 或 PRs，除非未来得到明确授权。分别检查：1) spec/用户结果与付费转化，2) repository/_ref/Apple/成熟 OSS/API 复用及 exact version/commit/license，3) iOS/backend/domain/contract/queue/observability 架构，4) account/StoreKit/upload/delete/AI/data-residency/security/privacy/compliance，5) code quality、测试真实性和去冗余，6) 真机 UX、accessibility、failure/recovery 和 visual quality。运行最新 tests、typecheck/build、migration up/down、OpenAPI diff/generated Swift compile、Promptfoo eval/red team、必要的 real provider/Apple sandbox smoke，并实操受影响的 iPhone 流程，保存 initial/input/processing/success/failure/recovery 证据。所有 P0/P1 在当前 milestone 直接修复，随后重新执行受影响检查和 bounded changed-file cleanup。只有六类审查均 APPROVE + CLEAR、复用审计完整、证据可复现时才允许下一个 milestone。
```
