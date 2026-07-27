# StyleCapture Journey PRD

- 产品：独立 iPhone 付费 App
- 工作名：StyleCapture Journey（衣程）
- 首发市场：中国大陆 App Store
- 核心承诺：用自己的衣服，搞定 3–7 天旅行的逐日穿搭和去重行李
- 非目标：Feed、泛 AI 聊天、首发真人试穿、社交社区、3D 数字人

## 1. 用户结果

用户创建一次 3–7 天旅行 Journey，输入日期、城市、逐日活动与约束，只导入本次相关衣物，即可获得：

1. 每天/每个活动的一套主 Look 和一套条件备选。
2. 鞋、包、配饰、外搭和温差/下雨处理。
3. 去重后的打包清单、缺口清单与复穿逻辑。
4. 每个决定的简短解释和可局部替换入口。
5. 计划执行后的像素邮戳、明信片与衣装收藏。

North Star 是付费旅行 Verified Scene Success（paid VSS），并拆成两个不可混用的层级：`packing_proxy_vss` 是付费用户锁定计划且完成至少 70% 打包，只可用于 D30 早期信号；`confirmed_worn_vss` 是旅行结束后确认至少一天采用计划主 Look、备选 Look，或完成可追踪的局部替换且仍满足原计划硬约束，是 D90 扩量门槛。单日婚礼、面试、约会属于后续独立实验，不能与旅行样本合并。

## 2. 核心旅程

1. 用户从按目的地、天气或行李限制区分的旅行 App Store 页面或内容链接进入同一个旅行模板。
2. 输入城市日期、活动、dress code、步行强度、行李限制和体感偏好；也可上传行程截图，经 OCR/AI 结构化后必须人工确认。
3. App 要求至少 8 件能覆盖本次必要槽位的衣物，推荐选择 12–30 件；使用 PhotosPicker 批量导入，自动识别后由用户确认或纠正，不承诺固定纠错时长。
4. 免费生成第 1 天完整主 Look，并显示第 2–7 天、全部备选、跨日去重打包、缺口与天气修订的锁定摘要。
5. 用户以 ¥12 购买本次旅行包；购买失败、AI 失败和重复通知不会扣权益。订阅在首发技术上可配置，但在 60 天第二次独立付费 Journey 达到 25% 前不作为默认 CTA 或扩量依据。
6. 用户局部替换、锁定计划、勾选打包；天气或行程变化只重算受影响日。
7. 当天通过本地通知确认“穿了/换了”；记录替换原因。
8. Journey 结束生成“12 件搭 8 套”结果卡和不含精确行程/人脸的像素明信片。

## 3. P0 功能

### 3.1 Journey 建立

- P0 只有 3–7 天旅行模板。婚礼、面试、约会等单日场合必须在旅行数据之外单独立项、单独定价和单独验证。
- 字段：日期、城市、时区、活动、室内外、正式度、步行强度、行李额度、怕冷/怕热、禁忌、必须带单品。
- 天气：展示数据时间与来源；允许无定位手填城市；精确定位不是前置条件。
- 行程截图：解析内容不直接保存为真源，用户确认后写入结构化 Occasion。

### 3.2 本次衣物篮子

- 相册多选、拍照、商品/灵感截图导入。
- 上传前压缩、重复检测、失败重试与后台继续。
- 每个 Item 可快速纠正品类、颜色、保暖度、正式度、是否已拥有。
- 用户修正优先级高于模型回写；原图删除后，识别结果的可用性和降级必须诚实显示。

### 3.3 计划与打包

- 输出一个推荐计划与逐日/逐活动备选。
- 硬约束确定性校验：礼仪、天气、鞋履、保暖、步行、必须/排除、行李数量。
- LLM 只在封闭候选内排序与解释，不得发明用户拥有的衣物。
- 打包清单按 Item 去重，标注穿着日、复穿次数、洗衣需要和缺失槽位。
- 替换一个槽位时保持其他已锁定项，不整套推翻。
- 计划、打包和权益都支持幂等写入与离线 outbox。

### 3.4 商业化

- StoreKit 2 展示、购买、恢复和管理商品/订阅。
- 首发商业主张只有 ¥12 一次性旅行包：解锁第 2–7 天、全部备选、跨日去重打包、缺口和天气修订；已购计划跨设备恢复并永久只读可看。
- Pro 月订阅可作为非默认的技术配置，只有 60 天第二次独立付费 Journey 达到 25% 后才允许成为主 CTA；年订阅只在用户完成第二次付费 Journey 后展示。订阅可解锁完整衣橱同步、持续编辑、跨 Journey 偏好和像素档案，不能成为恢复已购旅行包的前提。
- 服务端权益账本以 Apple 已验证交易为依据，支持退款、撤销、续订、宽限期与重复通知。
- 付费墙必须明确交付、次数、有效期和自动续订信息；不得使用虚假倒计时或模糊积分。

### 3.5 像素留存层

- 首次 Journey 获得基础像素角色。
- 计划锁定、打包完成、实际穿着和 Journey 完成分别解锁衣装、邮戳或背景。
- 分享卡默认移除精确日期、酒店、位置、人脸和原始照片。
- P0 不做社区、关注、聊天、舞会、跑秀、付费皮肤或多人世界。

### 3.6 账户、隐私与生成内容

- 首发 18+，不进入 Kids Category；年龄门控不是仅依赖 App Store 年龄分级。
- 匿名主体可体验一次预览；购买、云同步和第二设备前必须绑定 Sign in with Apple。
- App 内可发起账户删除、查看进度和撤回同意。删除会立即撤销会话、停止后台任务，并清理数据库、对象存储、派生图、缓存和处理者副本；法定账务记录隔离保存且不再用于产品。
- 使用 PhotosPicker 选择照片，不请求整个相册权限；照片不进入 `UserDefaults`、Web storage、埋点、日志或模型训练。
- 中国大陆首发不向境外 AI 服务发送真人照片。任何个人信息（照片、行程/城市/场合、衣橱描述、自由文本等）发送给第三方 AI 处理者前，都要展示接收者、数据类别、用途、保存期限、删除路径和训练用途并取得适用同意；敏感个人信息取得单独同意。未同意时只使用本地/确定性降级，不得静默发送。
- AI 生成或合成图片在预览、下载和分享中同时保留可见“AI 生成/合成”标识与法规要求的隐式元数据。
- AI observability 只保存经过字段 allowlist 的脱敏元数据，并有明确 TTL；prompt/completion、照片、行程原文、HTTP body、cookie/token 和自由文本不进入 trace、评测、CI artifact 或备份。
- 中国大陆公开发布前完成 APP 备案，并根据实际模型与服务形态完成生成式 AI 备案或登记判断和展示要求。

## 4. 指标口径、服务质量与商业门槛

所有商业指标只使用互斥、可复算的唯一用户分母：

- `qualified_install`：符合 ICP、未来 30 天有真实 3–7 天旅行的唯一生产用户；排除员工、测试账号、重复设备/主体和非目标行程。
- `preview_eligible`：完成旅行约束输入且拥有至少 8 件覆盖必要槽位的可用衣物；`preview_completion = unique(preview_ready) / unique(preview_eligible)`。
- `eligible_paywall`：用户完成免费 Day 1 预览后的第一次生产付费墙；排除 sandbox、TestFlight、restore、重复曝光和已有 entitlement。
- `pack_conversion`：首次购买旅行包的生产用户 / 被分配旅行包 offer 的 `eligible_paywall` 用户。
- `subscription_conversion`：首次购买订阅的生产用户 / 被分配订阅 offer 的 `eligible_paywall` 用户；订阅未解锁为主 offer 前仅作诊断。
- `combined_paid_conversion`：首次生产付款用户 / 全部生产 `eligible_paywall` 用户；同一用户只计一次。
- `plan_lock_rate`：成功交付完整付费计划后锁定计划的唯一 Journey / 成功交付完整付费计划的唯一 Journey。
- `paid_packing_proxy_vss`：完成至少 70% 打包的付费锁定 Journey / 已到打包观察窗末端的付费锁定 Journey。
- `paid_confirmed_worn_vss`：旅行后确认至少一天采用计划主 Look、备选 Look，或完成可追踪局部替换且仍满足原计划硬约束的付费锁定 Journey / 已完成旅行后观察窗的付费锁定 Journey。未响应、无法确认和明确未采用计划都不得进入 numerator；另报 `post_trip_followup_response_rate`，不得用低回访率抬高 VSS。
- `60d_repeat`：60 天内第二个独立付费 Journey 已交付且在观察窗末未退款的首次付款用户 / `first_purchase+60d` 已成熟且首单未退款的首次付款用户。
- `refund_rate`：完成退款观察窗的生产订单中已退款订单占比。
- `gross_margin = (App Store net proceeds - refunds - attributed model/weather/storage/notification costs) / App Store net proceeds`。

每个事件必须携带 `journey_id`、伪名主体、`journey_template=travel_3_7_day`、`offer_arm`、`product_id`、本地化价格/币种、`store_environment`、获客来源、事件时间、eligibility reason、`test_user_flag` 与 cohort maturity；分母去重、排除和观察窗版本进入指标字典并随决策记录冻结。

每个 D90 指标独立冻结 cohort：conversion 使用决策截止日之前的全部生产 eligible paywalls；confirmed VSS 只使用 `trip_end+7d` 已成熟的付费锁定 Journey，scale 时 denominator ≥30；repeat 只使用 `first_purchase+60d` 已成熟且首单未退款的首次付款用户，scale 时 denominator ≥50；refund 只使用首购满 30 天的生产订单，scale 时 denominator ≥50。每项同时报告 numerator、denominator、cohort start/end 和 maturity cutoff，不得用总 payer 数替代成熟分母。

| 指标 | P0 目标 |
|---|---:|
| qualified install → Journey started | ≥60% |
| preview eligible → preview ready | ≥40% |
| 生产 eligible paywall → 首次付款 | ≥8%（D90，且以旅行包为主） |
| 付费完整计划交付 → 锁定 | ≥75% |
| 成熟付费锁定 Journey → confirmed worn VSS | ≥55% |
| P50 / P90 首次个性化预览 | <5 分钟 / <10 分钟 |
| AI/天气/存储可变成本 | ≤净收入 25% |
| 场景包毛利 | ≥65% |
| crash-free sessions | ≥99.5% |
| 严重天气/礼仪约束错误 | <2% |
| AI 失败不扣权益 | 100% |
| 付费资产丢失 | P0 = 0 |

## 5. 埋点合同

事件名固定、字段最小化，不记录照片、行程原文、精确位置、自由文本或 provider payload：

- `journey_started`
- `itinerary_confirmed`
- `garment_import_started/completed/corrected`
- `preview_ready/failed`
- `paywall_viewed`
- `purchase_started/completed/failed/restored/refunded`
- `paid_plan_delivered/failed`
- `plan_slot_replaced`
- `plan_locked`
- `packing_progressed`
- `outfit_worn_confirmed`
- `journey_completed`
- `pixel_memento_shared`
- `account_deletion_started/completed`

所有业务事件带上述指标合同字段以及 App 版本、entitlement tier、耗时和枚举错误码；服务端生成的 AI 成本与结果事件通过短期不透明 request/trace ID 关联，不把模型细节暴露给客户端。首次价值时间从 `journey_started` 到 `preview_ready`，同时报告 active input time 与 server wait time，避免把用户录入时间误算成模型延迟。漏斗必须分别报告 purchase → `paid_plan_delivered` 与 delivered → `plan_locked`，不得用购买成功掩盖未交付，或用锁定率掩盖生成失败。

## 6. 发布门禁

首发必须同时满足：

- M0 在 7 天内完成招募/报价，最终 GO 只在至少 15 名 plan recipients 达到 `trip_end+7d` 后判断并记录实际 maturity cutoff：`pain_rate = 痛点评分≥7 的 qualified interviewees / 完成痛点题的全部 qualified interviewees`，denominator ≥20 且 rate ≥60%；`real_paid_rate = 实际支付或可退款订金的唯一用户 / 收到完整计划并看到唯一 ¥12 offer 的全部合格用户`，denominator ≥15、rate ≥33% 且 payer ≥5；`execution_rate = 至少一天采用计划主/备选 Look 或符合原硬约束的可追踪局部替换的用户 / trip_end+7d 已成熟的全部 plan recipients`，未回访按未执行，denominator ≥15 且 rate ≥50%。三项同时通过才 GO；`real_paid` 不接受意愿、口头或“等价承诺”。
- TestFlight 仅验证 activation、preview、plan quality、lock、restore 和技术购买链路；sandbox/TestFlight 交易不得计入 willingness-to-pay、生产转化、收入、退款或毛利。
- 商业软启动至少获得 200 个生产 `eligible_paywall` 与 20 个真实付款后才可声称初步付费验证；扩量门槛使用至少 500 个生产 `eligible_paywall` 与 50 个真实付款的成熟 D90 cohort。
- StoreKit sandbox、TestFlight 与 App Store Server Notifications V2 恢复演练通过。
- 无效 SIWA audience/nonce/replay 全部拒绝；账号删除后旧 token 立即失效。
- 账号删除、照片/行程删除、处理者删除、订阅恢复、AI 失败返权益、离线重试通过。
- PrivacyInfo.xcprivacy、App Privacy、隐私政策、用户协议、生成内容显式/隐式标识审计通过。
- 抓包与 provider-side sentinel 证明取得适用同意前，不向任何第三方 AI 处理者发送照片、行程/城市/场合、衣橱描述、自由文本、稳定主体标识、cookie/token 或其他个人信息；本地/确定性降级仍可用。中国用户路径不调用未完成合规的境外真人图片处理者。
- Langfuse/OTel/Promptfoo 隐私 canary 证明敏感标记在应用、Collector、数据库/ClickHouse/blob、队列、缓存、日志和 CI artifact 中零命中；删除账户后相关 trace/dataset/eval 副本也经轮询确认消失。
- 自动续费前至少 5 日提供不依赖通知权限的 App 内显著提醒，并在已授权时辅以通知，展示日期、金额、周期和取消入口；删除账户明确说明不会自动取消 App Store 订阅并直达系统订阅管理。
- APP 备案、适用的生成式 AI 备案/登记与 18+ 策略完成。
- 真机覆盖小屏/主流/大屏、弱网、后台恢复、低存储、权限拒绝、动态字体、VoiceOver。
- 无 P0/P1 安全、隐私、数据丢失、付费或严重穿搭约束缺陷。
- 现有单场景、拼贴或 provider-bound Skill 输出不得替代 iOS Journey 证据。任何未来 Skill/App Intent 必须走与 App 相同的 Product API/domain/provider、权益、成本、删除和观测路径；P0 不发布可下载 Agent Skill。

任何一个 kill trigger 成立即停止扩量并 PIVOT/STOP 当前旅行楔子：两轮各至少 100 个生产 `eligible_paywall` 且质量门通过后，合并首次付费转化仍 <3%；至少 50 个成熟付费锁定 Journey 的 `paid_confirmed_worn_vss` <30%；至少 100 个付费 Journey 且做过一次成本优化后毛利仍 <40%；或至少 20 个流失访谈中 ≥60% 的首要原因是结果没有货币价值。迭代区间采用不重叠半开边界：`3% ≤ conversion <8%`、`30% ≤ confirmed VSS <55%`、`10% ≤ 60d repeat <25%`、`40% ≤ gross margin <65%`。Scale 只有在成熟样本和所有 scale gate 同时满足时成立。
