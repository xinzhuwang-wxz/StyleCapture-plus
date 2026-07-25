# PR12 移动端全生命周期 AutoResearch 报告

## 第 5 轮最终收口：通过

时间：2026-07-26
分支：`codex/pr12-main-integration`
视口：390 × 844 模拟手机
结论：前端、API、领域、持久化与真实托管模型边界已完成回归；第 4 轮多角色审查发现的两个 P1 均在本分支修复并复验，当前没有未解决 P0/P1。

### 真实用户路径

- 首屏进入 Feed；圈选入口在播放/暂停状态均可进入，首次进入显示画圈手势提示。
- 前两个 Feed 在圈选闭合并浮起主体后继续提示“左划取消 / 右划加入”，补齐首次用户从圈选到决策的完整教学。
- 实际点击“一键保存整套穿搭”后，主体浮起并要求用户确认；确认后真实写入数字衣橱。
- 保存完成后在 Feed 内出现不阻断浏览的“顺手记一下喜欢它哪里？”提示；选择“层次感”后提示消失并继续停留 Feed。
- 衣橱一级卡片使用像素资产，详情保留真实单品、来源、分类、标签和搭配关系。
- 18 组已策展的“实物图 ↔ 像素图”自有衣物按固定展示序前置；后续 Feed、上传和拍照入库内容继续按新鲜度排在其后。
- 实际选择 HEIC 文件并提交为“单件衣服 / 我的衣服”，进入异步转换与识别状态。
- 短时启动 LiteLLM 后，AI 基于真实衣橱逐步返回 4 套中文穿搭，随后以场景理解完成重排；验证完成即停止 LiteLLM，本地 AI Worker 全程关闭。

最终截图：`docs/evidence/pr12-integration/40-autoresearch-feed-liking-prompt-final.png`、`41-clean-curated-items-first.png`、`42-feed-post-lasso-swipe-guide.png`。

### 最终验证

- Backend 全量：`.venv/bin/pytest -q` → `289 passed in 9.22s`
- 上传删除生命周期：临时上传可撤销；已绑定 capture 的上传返回 HTTP 409 且原图保留，相关定向测试 `30 passed`
- Python 静态检查：Ruff 通过；Mypy `102 source files` 无问题
- H5：`12 files / 83 tests passed`；typecheck 与 production build 通过
- 容器增量重建：API/H5 healthy；仅运行 API、H5、PostgreSQL、Redis
- 资源快照：H5 约 `0.23% CPU / 9.35 MiB`，API 约 `7.75% CPU / 246 MiB`，无本地重模型满载
- `git diff --check`：通过

### 本轮审查闭环

1. 数据生命周期 P1：上传在 capture 提交后仍可由临时删除入口移除。
   - 修复：删除入口只能调用 `discard_unattached_upload`；已挂载对象返回稳定 `upload_already_attached` / 409。
   - 证据：存储层与 HTTP 层回归均覆盖未挂载成功删除、已挂载拒绝删除。
2. 用户偏好 P1：保存整套后的喜欢原因提示被渲染在隐藏的衣橱容器中。
   - 修复：提示移动到 Feed 可见区域并保留可跳过设计。
   - 证据：H5 回归通过，390 × 844 实操完成“保存整套 → 提示出现 → 选择层次感 → 继续 Feed”。
3. 首次圈选教学 P1：只教用户画圈，没有说明圈选后如何完成或取消。
   - 修复：前两个 Feed 的闭合圈选进入确认态时显示“左划取消 / 右划加入”，同时保留直接点击两侧操作的无障碍路径。
   - 证据：390 × 844 模拟手机实际沿人物画圈并看到提示；`feed-selection-overlay` 回归覆盖完整画圈到滑动提示状态，H5 全量 `83 passed`。
4. 演示数据整洁性：AutoResearch 留下的上传与 Feed 测试记录污染当前衣橱。
   - 修复：仅删除当前本地演示用户的 12 条非 curated capture、9 个测试单品和 4 个测试 Look；28 个预置单品和 3 个预置 Look 保留。
5. 模型路由：套装搭配关系分析按产品最终决策从 Mini 切回 Lite；模型 ID 仍只存在于 LiteLLM 基础设施配置中。
6. 预置升级兼容性：已有演示用户的策展元数据升级改变像素输入签名，旧的固定 request key 触发 409。
   - 修复：策展像素展示的幂等键纳入输入签名摘要；相同输入保持幂等，真实变化生成新版本，不覆盖旧产物。
7. 浏览器会话残留：已被后台清理的测试 job 仍可能从 sessionStorage 恢复为永久“处理中”。
   - 修复：只在 API 明确返回 `job_not_found` 时移除本地占位；暂时性网络失败仍保留可恢复状态。

AutoResearch 停止条件“完整多角色审查无新 P0/P1”已满足；后续工作进入 PR 整理、合并与部署。

## 第 4 轮低负载修复验证（电脑发热保护）

时间：2026-07-26 06:02
分支：`codex/pr12-main-integration`
模式：低负载；未启动 Docker、未跑模型/生图、未跑浏览器 E2E。
资源：`uptime` load averages `4.85 4.85 4.64`；当前磁盘剩余 `73GiB`。
结论：第 3 轮发现的多项 P1 已有代码与单测证据闭环，但由于本轮按用户要求保护主机，没有执行 390×844 真实移动端复验，因此不能把本轮标记为最终 approved。

### 已修复并验证

1. HEIC / pending 重复渲染风险
   - 验证：`pnpm --filter @stylecapture/h5 test -- --run apps/h5/tests/app.test.tsx apps/h5/tests/look-wardrobe.test.tsx`
   - 结果：`12 files / 80 tests passed`
   - 说明：H5 当前测试集覆盖 HEIC pending、Feed 状态机、Look 刷新恢复、AI Look 来源文案等关键断言。

2. 用户上传非单件服装误入库
   - 修复：上传图片在创建 WardrobeItem 前先做候选归一化；多件服装、无可靠服装、源图缺失不会新建“其他”单品污染衣橱。已有 retry item 会进入 ERROR。
   - 验证：`.venv/bin/pytest -q services/backend/tests/worker/test_capture_processing.py` → `10 passed`

3. 上传 token replay / 存储消耗风险的第一层防线
   - 修复：`LocalObjectStore.accept_upload()` 成功写入前后使用 `.upload-tokens/{sha256(token)}.json` 原子 claim；成功后的 token 不能再次上传。
   - 验证：`.venv/bin/pytest -q services/backend/tests/capture/test_local_object_store.py services/backend/tests/worker/test_capture_processing.py` → `20 passed`

4. 预置 seed 原图和展示图分离
   - 修复：curated seed 使用独立 source/display object key；老 seed 可幂等升级展示图，不覆盖用户修正标签。
   - 验证：`.venv/bin/pytest -q services/backend/tests/wardrobe/test_curated_demo.py services/backend/tests/api/test_session_seed_quota.py` → `10 passed`

5. 多业务共享上传图的物理删除风险
   - 修复：真人试穿和像素试玩删除只解绑当前业务/删除派生产物，不再物理删除共享 subject；Look source 删除入口不再暴露为危险物理删除，H5 隐藏删除整套原图按钮。
   - 验证：`.venv/bin/pytest -q services/backend/tests/api/test_look_http.py services/backend/tests/render/test_render_http.py services/backend/tests/pixel_trial/test_pixel_trial_http.py` → `10 passed`

### 合并后的轻量回归

- 后端定向回归：
  - `.venv/bin/pytest -q services/backend/tests/capture/test_local_object_store.py services/backend/tests/worker/test_capture_processing.py services/backend/tests/wardrobe/test_curated_demo.py services/backend/tests/api/test_session_seed_quota.py services/backend/tests/api/test_look_http.py services/backend/tests/render/test_render_http.py services/backend/tests/pixel_trial/test_pixel_trial_http.py`
  - 结果：`41 passed in 0.67s`
- H5 typecheck：
  - `pnpm --filter @stylecapture/h5 typecheck`
  - 结果：通过
- H5 单测：
  - `pnpm --filter @stylecapture/h5 test -- --run apps/h5/tests/app.test.tsx apps/h5/tests/look-wardrobe.test.tsx`
  - 结果：`12 files / 80 tests passed`
- 静态检查：
  - `git diff --check`
  - 结果：通过
- Python 语法编译：
  - `python3 -m py_compile ...object_store.py ...processing.py ...look/interfaces/http.py ...render/interfaces/http.py ...pixel_trial/interfaces/http.py`
  - 结果：通过

### 仍需在降温后完成的真实移动端复验

不能省略。下一轮需要在 390×844 模拟手机里亲自点击验证：

1. Feed 首屏 → 暂停/恢复 → 圈选按钮始终可用 → 教学手势 → 存单品/存整套。
2. 上传 JPEG/PNG/HEIC → 单件成功入库 → 多件/非服装给出可恢复错误，不污染衣橱。
3. 衣橱一级像素风展示 → 点击详情保留真实图、来源、分类和搭配关系。
4. AI 推荐流式/逐套展示 → 保存 Look → 刷新恢复刚保存的 Look 详情。
5. 真人试穿 / Try 像素 / 像素封面失败和重试路径。

---

## 第 3 轮报告（历史拒绝记录）

时间：2026-07-26
分支：`codex/pr12-main-integration`
视口：390 × 844 移动端
结论：未通过。第 3 轮仍发现 P1，不能把 `.omx/specs/autoresearch-pr12-mobile-lifecycle/result.json` 标为 approved。

## 验证覆盖

- 真实移动端路径：Feed 首屏、暂停/恢复/圈选入口、衣橱入口、AI 推荐、保存 Look、Look 详情、刷新恢复。
- 自动化测试：H5 关键测试、Backend HEIC/render/pixel 相关测试。
- 资源守门：Docker 容器 CPU/内存快照。
- 代码证据：HEIC pending、Look source 状态、AI rationale、failure message 展示路径。

## P1 阻塞

### P1-1：HEIC pending UI 重复渲染，导致测试失败和 React key 冲突

复现：

1. 运行 H5 关键测试。
2. 触发 HEIC upload pending 卡片。

实际：

- `apps/h5/tests/app.test.tsx > keeps HEIC upload usable without rendering a broken browser preview` 失败。
- Testing Library 发现多个 `role="status"` 且 name 为空的 `.pending-heic-preview`。
- React 控制台警告重复 key：`33333333-3333-4333-8333-333333333333`。

期望：

- 同一次 HEIC pending 只出现一个清晰状态节点。
- pending card 有稳定唯一 key，不能重复插入同一个 job。
- 可访问性查询不应被隐藏/重复节点污染。

证据：

- 命令：`pnpm --dir apps/h5 test -- --run tests/app.test.tsx tests/feed-runtime.test.tsx tests/feed-selection-overlay.test.tsx tests/look-wardrobe.test.tsx tests/ai-recommend.test.tsx`
- 结果：`12 test files, 75 tests；73 passed, 2 failed`
- 相关代码：
  - `apps/h5/src/features/wardrobe/ItemCard.tsx`
  - `apps/h5/src/features/profile/ProfileScreen.tsx`
  - `apps/h5/src/features/wardrobe/LookDetail.tsx`

### P1-2：Feed 暂停/圈选状态机仍不够稳定

复现：

1. 打开首屏 Feed。
2. 在视频区域点击画面。
3. 再点击画面或圈选入口。

实际观察：

- 首屏是 Feed，第一条圈选按钮可用。
- 但一次点击后出现过 `捕捉中`，同时第一条 `暂停并圈选` disabled。
- 第二次点击后才出现 `一键存整套 / 沿衣服边缘画一圈 / 轻点画面可继续播放`。
- 这和“暂停后圈选始终常亮、点屏幕可恢复播放”的目标仍有偏差。

期望：

- 点击画面：只暂停/恢复，不应误进入捕捉中。
- 圈选按钮：当前可见 Feed 上始终常亮可点；点击后定帧并进入圈选引导。
- 暂停状态下再次点击画面应恢复播放，除非用户正在实际画圈。

证据：

- 浏览器实操状态：`firstCircleDisabled: true`、`captureText: true` 出现在点击画面后的状态。
- DOM 还同时存在 30 条 Feed 的按钮，只有第一条可用，其余 disabled；这增加了状态机和测试定位复杂度。

### P1-3：AI 保存 Look 详情使用“原始画面已删除”，对 AI 搭配来源不真实

复现：

1. 进入 AI 推荐。
2. 输入中文场景需求。
3. 保存一套方案。
4. 打开保存后的 Look 详情。

实际：

- Look 来源是 AI 搭配保存，但 hero 缺省时显示 `原始画面已删除`。
- 这会让用户误以为图片丢失，实际它本来就不是 Feed/上传原图来源。

期望：

- AI 生成 Look 应显示类似：`由 AI 推荐保存`、`无原始画面来源`、`真实单品与生成结果已保留`。
- 只有 Feed/上传来源真的被删除时，才显示“原始画面已删除”。

证据：

- 相关代码：`apps/h5/src/features/wardrobe/LookDetail.tsx`
- 当前逻辑：heroImageUrl 为空时固定 `<small>原始画面已删除</small>`。

### P1-4：Look 详情刷新后丢上下文，未满足“刷新恢复”

复现：

1. 从 AI 推荐保存 Look。
2. 点击进入 Look 详情。
3. 刷新页面。

实际：

- 页面回到 Feed 首屏。
- 用户刚保存的 Look 详情上下文丢失。

期望：

- 至少恢复到刚才的 Look 详情，或恢复到衣橱并高亮/提示最近保存的 Look。
- pending render / processing 状态不应因为刷新失去用户可追踪入口。

证据：

- 浏览器实操：保存 Look 后进入详情，reload 后 `location=http://localhost:5173/` 且 Feed 可见。

### P1-5：AI 推荐“逐套出现”与实际批量出现不一致

复现：

1. 进入 AI 推荐。
2. 输入需求并提交。

实际：

- 等待后一次性展示 4 套方案。
- 文案写：`新方案会逐套出现，AI 正在继续理解和细化。`

期望：

- 如果目标是“生成一套出一套”，前端应真实逐套 append 或以流式/轮询状态体现。
- 如果后端当前只能批量返回，应改文案，不能暗示逐套实时生成。

证据：

- 相关代码：`apps/h5/src/features/ai/AIRecommendScreen.tsx`

## P2 改进

### P2-1：中文业务文案仍有英文标点

实际：

- AI rationale 生成：`安排层次, 以协调为主线; ...`

期望：

- 全中文标点：`安排层次，以协调为主线；...`

证据：

- 相关代码：`services/backend/src/stylecapture_backend/features/outfit/application.py`

### P2-2：Feed DOM 全量渲染 30 条，对可访问性和测试定位不友好

实际：

- 首屏 body text 包含大量 Feed 条目。
- 30 个 `暂停并圈选` 按钮都在 DOM 中，除当前条外 disabled。

期望：

- 只暴露当前可见 Feed 的交互节点，或对非当前条设置明确隐藏/不可访问。

### P2-3：删除原图测试期望落后于新文案

实际：

- 测试期望：`删除后原图无法恢复`
- 产品实际文案：`删除后原始上传图无法恢复；抠出的单品图、分类、描述和归属仍会保留。保留原图确认删除原图`

判断：

- 新文案更准确，这个更像测试需要更新，不是产品缺陷。

## 通过项

- 首屏默认进入 Feed，而不是衣橱。
- 当前 Feed 至少存在可点击的第一条圈选入口。
- 衣橱一级界面采用像素风展示，详情保留真实资产入口。
- AI 推荐可以基于衣橱数据生成多套中文穿搭，并支持保存 Look。
- Backend HEIC / render / pixel 关键路径测试通过：
  - 命令：`.venv/bin/pytest services/backend/tests/api/test_wardrobe_http.py services/backend/tests/api/test_look_http.py services/backend/tests/item_presentation/test_item_presentation_processing.py services/backend/tests/item_presentation/test_item_presentation_http.py services/backend/tests/pixel_trial/test_pixel_trial_processing.py services/backend/tests/render/test_image_inputs.py services/backend/tests/render/test_render_processing.py -q`
  - 结果：`28 passed in 1.60s`
- Docker 资源快照未满载：
  - `stylecapture-api-1 40.73% CPU / 262.4MiB`
  - `stylecapture-worker-ai-light-1 0.20% CPU / 962.7MiB / 2GiB`
  - `stylecapture-litellm-1 320.7MiB / 768MiB`

## HEIC 结论

- 后端 HEIC 处理和 render/pixel 路径已有测试通过。
- UI 自动化里 HEIC pending 暴露了重复状态问题，因此 HEIC 端到端仍不能算通过。
- 浏览器运行时对真实 HEIC 文件选择存在工具限制，不能把上传工具失败当作产品失败；但 H5 单测已经足够证明 pending UI 有缺陷。

## 验收结论

本轮 AutoResearch 不能批准。必须先修复 P1-1、P1-2、P1-3、P1-4；P1-5 至少要二选一：真实逐套输出或修改文案。修完后重新跑：

1. H5 关键测试。
2. Backend HEIC/render/pixel 测试。
3. 390×844 真实移动端路径：Feed 暂停/恢复/圈选、上传 HEIC pending、AI 推荐保存 Look、Look 详情刷新恢复。
