# 真人试穿 Skill 1.4.3 交接文档

更新时间：2026-08-10（Asia/Shanghai）

## 1. 当前工作区

- 工作区：`C:\Users\27476\Documents\Codex\2026-08-08\xinzhuwang-wxz-stylecapture-plus-https-github\work\ui-polish-capture-share`
- 当前分支：`main`
- 基准提交：`45d4ea5`（Merge pull request #82）
- 前端测试地址：`http://localhost:5176/`
- API：`http://localhost:8002/`
- 2026-08-10 已验证：`8002/healthz` 和 `5176/healthz` 均返回 HTTP 200。

> 重要：当前真人试穿修改尚未提交，而且直接位于一个显示为 `main` 的脏工作区。不要运行 `git reset --hard`、`git checkout -- .` 或直接 pull 覆盖。建议下一窗口先从当前状态创建功能分支，再提交。

## 2. 用户反馈与本轮目标

此前真人试穿存在两个相互叠加的问题：

1. 生成结果可能出现五官变化、身体纵向压缩、头身比异常、宽松衣服被生成成紧身、服装颜色偏移。
2. 质量审计过严：即使豆包已经成功生成图片，只要审计不通过，后端就丢弃结果并降级为“真实单品拼贴”，导致用户一直看到“未通过身份、比例或服装保真审计”，完全拿不到试穿图。

本轮优先目标不是声称每张图都完美，而是保证：

- 合格输入成功调用生图后，至少返回一张候选试穿图；
- 审计用于重试、排序和记录问题，不再吞掉全部生成结果；
- 最多两次生成，目标等待时间不超过用户可接受的 1–2 分钟；
- 保留身份、身体比例、服装颜色和版型约束，便于后续继续调优。

## 3. Skill 1.4.3 现在的工作方式

### 3.1 输入照片门槛

生图前先用视觉理解模型检查人物覆盖范围。

可接受条件：

- 人物从颈部、肩部开始连续可见；
- 躯干、髋部、双膝可见；
- 双膝下方至少有一段有意义的小腿区域；
- 脚踝和双脚可以不出现；
- 眼镜、轻微模糊、贴纸或脸部局部遮挡本身不作为拒绝理由。

拒绝条件：照片在膝盖以上、膝盖处或大腿处被裁掉，无法可靠维持身体比例。拒绝发生在付费生图之前。

### 3.2 鞋子规则

如果原图已经到小腿或脚踝、但没有显示双脚，而目标穿搭包含鞋子：

- 不强行把鞋塞进画面；
- 跳过鞋子替换；
- 不扩图、不凭空补脚、不缩短腿、不增大头部，也不改变镜头距离。

这是为了修复“为了露鞋而把腿压短”的问题。

### 3.3 身份与身体规则

- 人物原图是唯一身份来源；
- 要求保留可见的五官几何关系，而不是只追求“相似风格”；
- 脸是否高清不是硬门槛，但可见五官不能被重新设计；
- 保留头部像素尺寸、头身比、肩线、躯干长度、髋部位置、姿势、裁切、镜头和背景；
- 不根据审美凭空生成更瘦、更丰满或更理想化的身体；
- 原衣服遮住身体轮廓时，只做保守的结构连续推断。

### 3.4 服装规则

- 穿搭板是唯一服装来源；
- 保留衣服的真实颜色、明度、冷暖倾向、纹理和杂色效果；
- 保留版型、松量、肩线、褶皱和垂坠；
- 宽松、箱型、廓形、喇叭或垂坠款不能因为原图穿着紧身衣而变紧身；
- 不保留原图衣服和配饰，除非穿搭板中也出现同一件物品。

### 3.5 两次候选与等待时间

- 默认最多生成 2 次，不是无限重试；
- 第 1 张严格通过审计时立即返回，不生成第 2 张；
- 第 1 张不严格通过时，审计给出修正建议，再生成第 2 张；
- 最终按“严格通过 > 可复核 > 综合分最高”选择最佳候选；
- 之前容器日志中单次任务通常约 7–9 秒，但外部豆包服务可能波动；产品预算按 1–2 分钟封顶理解。

### 3.6 本轮最关键变化：审计不再吞图

旧逻辑：

`生成成功 -> 审计失败 -> 进程返回 3 -> 后端丢弃图片 -> 降级成拼贴图`

新逻辑：

`生成成功 -> 审计并排序 -> 返回最佳候选 -> 把风险写入 provider_trace`

只有以下情况仍会阻断：

- 输入照片覆盖范围不合格；
- 豆包/API/网络调用失败；
- 生成文件缺失、为空或格式无效。

生成完成后的质量状态分为：

- `pass`：严格通过；
- `review_required`：可用，但审计分数偏保守；
- `needs_attention`：有明显审计风险，但仍返回最佳已生成图片，避免用户完全拿不到结果。

后端 `provider_trace` 会保存：

- 选中的 attempt；
- `hard_pass`；
- `audit_release_eligible`；
- `delivery_eligible`；
- `quality_status`；
- 身份、身体、服装、真实感分数；
- 五官是否变化、头身比、纵向压缩、版型是否泄漏等摘要。

这让下一窗口可以根据真实失败原因继续调 Skill，而不是只看到统一的泛化错误。

## 4. 主要修改文件

- `skills/doubao-virtual-try-on/scripts/virtual_try_on.py`
  - Skill 版本升级为 1.4.3；
  - 放宽合理的小腿覆盖输入；
  - 增加鞋子跳过、颜色、版型、身体结构约束；
  - 增加两层审计与审计摘要；
  - 成功生成后始终交付最佳候选。
- `skills/doubao-virtual-try-on/SKILL.md`
  - 同步输入门槛、鞋子规则、服装保真和“审计用于排序而非吞图”的流程。
- `services/backend/src/stylecapture_backend/features/render/infrastructure/providers.py`
  - 接受 `delivery_eligible`；
  - 保存 1.4.3 的审计摘要到 provider trace。
- `services/backend/src/stylecapture_backend/features/render/prompt_contracts.py`
  - Pipeline 版本升级为 `doubao-virtual-try-on-skill-v1.4.3`。
- `services/backend/tests/render/test_render_providers.py`
- `services/backend/tests/render/test_render_processing.py`
- `services/backend/tests/render/test_render_signatures.py`
- `tests/test_doubao_skill.py`
  - 覆盖输入拒绝、严格通过、复核结果、`needs_attention` 仍然交付等行为。
- `apps/h5/vite.config.ts`
  - 本地 Vite API proxy 可配置，用于让 5176 指向 8002。

## 5. 已完成验证

本轮测试结果：

- Skill 单元测试：13/13 通过；
- 后端 render provider/processing/signature 测试：30/30 通过；
- Ruff：通过；
- Skill Creator `quick_validate.py`：通过；
- `git diff --check`：通过；
- API 8002 健康检查：HTTP 200；
- 前端 5176 代理健康检查：HTTP 200。

关键回归测试已经模拟：即使审计返回五官变化、头身比异常、纵向压缩、版型泄漏等严重风险，只要图片确实生成成功，Skill 仍以 `needs_attention` 返回最佳图片，后端不再自动降级成拼贴。

## 6. 当前未提交文件

交接时 `git status --short` 包含：

```text
 M apps/h5/vite.config.ts
 M services/backend/src/stylecapture_backend/features/render/infrastructure/providers.py
 M services/backend/src/stylecapture_backend/features/render/prompt_contracts.py
 M services/backend/tests/render/test_render_processing.py
 M services/backend/tests/render/test_render_providers.py
 M services/backend/tests/render/test_render_signatures.py
 M skills/doubao-virtual-try-on/SKILL.md
 M skills/doubao-virtual-try-on/scripts/virtual_try_on.py
 M tests/test_doubao_skill.py
?? .tmp/
```

`.tmp/` 是此前已经存在且当前不可读的未跟踪目录，未在本轮删除或修改。提交时不要直接 `git add .`，应明确添加上面的目标文件和本交接文档，避免误收 `.tmp/`。

## 7. 下一窗口建议操作顺序

1. 先在当前脏工作区创建功能分支，保留所有未提交修改。
2. 硬刷新 `http://localhost:5176/`。
3. 用用户认为合格的两张照片分别生成真人试穿：
   - 镜子全身照，显示到脚踝；
   - 户外照，显示到双膝以下小腿，但不显示脚。
4. 确认前端不再显示统一的“审计失败，已保留拼贴”，而是能拿到最佳试穿图。
5. 查询最新 try-on artifact 的 `provider_trace`，记录：
   - `quality_status`；
   - `selected_attempt`；
   - `audit_summary`；
   - 实际耗时。
6. 若图仍不理想，优先根据审计摘要只改一类问题，不要一次堆更多提示词：
   - 五官变化；
   - 身体纵向压缩；
   - 服装颜色偏移；
   - 宽松版型变紧；
   - 无脚照片误套鞋。
7. 做 3–5 组固定回归样本，比较每次修改前后的命中率和耗时，再决定是否提交 PR。

## 8. 设计取舍与后续风险

- 当前策略优先解决“完全没有结果”的产品阻塞，因此 `needs_attention` 也会交付。它不等于图片质量已经合格。
- 不建议同时生成很多候选。当前最多两张是质量、费用和 1–2 分钟等待预算之间的折中。
- 提示词继续增长可能互相稀释。后续应优先把可测事实放到结构化理解结果中，再由脚本生成短且有优先级的确定性提示词。
- 结构审查暂未加入单独的第三阶段，符合用户当前要求；先观察 1.4.3 实际结果，再决定是否增加。
- 不要用真实用户照片做未经授权的后台重复提交。需要重跑用户图片时，应在前端由用户主动触发，或先取得明确授权。

## 9. 常用验证命令

```powershell
cd "C:\Users\27476\Documents\Codex\2026-08-08\xinzhuwang-wxz-stylecapture-plus-https-github\work\ui-polish-capture-share"

$env:TEMP="$PWD\.test-tmp"
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

.\.venv\Scripts\python.exe -m unittest tests.test_doubao_skill
.\.venv\Scripts\python.exe -m pytest services/backend/tests/render/test_render_providers.py services/backend/tests/render/test_render_processing.py services/backend/tests/render/test_render_signatures.py -q
.\.venv\Scripts\ruff.exe check skills/doubao-virtual-try-on/scripts/virtual_try_on.py services/backend/src/stylecapture_backend/features/render/infrastructure/providers.py
```

容器重建：

```powershell
docker compose build api worker
docker compose up -d --force-recreate worker
$env:STYLECAPTURE_API_PORT="8002"
docker compose up -d --force-recreate api
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8002/healthz
Invoke-WebRequest -UseBasicParsing http://localhost:5176/healthz
```

## 10. 2026-08-10 续作记录

本窗口已把原脏工作区原样切到功能分支：

`codex/virtual-try-on-skill-1.4.3`

新增完成项：

- 后端不再把所有 Skill 输出固定标为 JPEG；现在按字节签名识别 JPEG、PNG、WebP，并拒绝
  空文件和无效图片。
- 批量 Skill 与单图语义对齐：严格通过优先，但已成功生成的批量结果不会因跨 Look 审计
  保守而全部丢弃；非严格通过标记为 `needs_attention`。
- 打包器版本从遗留的 1.3.0 同步到 1.4.3，默认产物为
  `dist/skills/doubao-virtual-try-on-v1.4.3.zip`。
- 新增 ADR-0008，并同步 TECHNICAL-DECISIONS、ExecPlan 0054 和独立 Skill 文档，旧的
  “只有 hard_pass 才交付”契约已被正式取代。
- 修复 Compose 密钥变量兼容：本地 `.env` 使用 `STYLECAPTURE_ARK_API_KEY`，原 Compose
  只读取 `ARK_API_KEY`，会静默注入空值。现在 Worker、AI-light Worker、LiteLLM 都兼容两种
  名称，并优先使用 product-prefixed 名称。

新鲜验证：

- Skill：14/14 通过。
- 后端 Render：31/31 通过。
- Ruff、focused mypy、Skill Creator `quick_validate.py`、Skill 打包、Compose YAML 解析、
  `git diff --check`：通过。
- H5 typecheck：通过。
- H5 try-on 目标测试：4/4 通过。
- H5 production build：通过。
- H5 全量测试另有 6 个未改动的 `feed-runtime.test.tsx` 失败，应独立处理；本轮 try-on
  用例没有失败。
- API/Worker 已重建并确认运行
  `doubao-virtual-try-on-skill-v1.4.3`；8002 与 5176 health 均为 200。

后续重启结果：

- 已重新创建 `litellm` 与 `worker`。
- `STYLECAPTURE_ARK_API_KEY` / `ARK_API_KEY` 非空布尔值均为 `True`，未打印密钥。
- API、LiteLLM、Worker 均 healthy；Worker 报告
  `doubao-virtual-try-on-skill-v1.4.3`；8002 与 5173 health 均为 200。

尚未执行：

无阻塞项。用户已在 H5 主动完成一张授权照片的真实试穿：

- 状态：`succeeded`
- `quality_status`：`needs_attention`
- `selected_attempt`：1
- 总耗时：约 229 秒
- 身份 / 身材 / 服装 / 真实感：83 / 91 / 88 / 92
- 头身比、纵向比例、目标服装版型：通过
- 人脸：`facial_features_changed=true`，仍有可见走形

本轮决定先提 PR。继续把人脸从 83 稳定提升到“近乎同一个人”不再视为简单追加提示词；后续应
作为身份保持专项，比较更强的 reference-conditioned 编辑、局部脸部重绘或专门 Face-ID 约束，
并用固定授权样本做重复命中率测试。
