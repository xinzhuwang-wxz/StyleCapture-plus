## 独立商业 App 路线（长期分支）

`codex/stylecapture-journey` 在不急于合并的独立分支上验证一个新的付费楔子：
3–7 天旅行的逐日穿搭和去重打包计划。单日婚礼、面试、约会不进入同一 P0 或指标分母。
该路线不复制 Feed，也不改变本文件记录的原演示产品。
商业路线的当前真源为：

- `docs/product/STYLECAPTURE-JOURNEY-PRD.md`
- `docs/architecture/STYLECAPTURE-JOURNEY-TECHNICAL-DESIGN.md`
- `docs/architecture/JOURNEY-SKILL-CAPABILITY-REGISTRY.md`
- `docs/research/STYLECAPTURE-JOURNEY-MARKET-AND-REUSE-AUDIT.md`
- `docs/exec-plans/0043-stylecapture-journey-commercial-app.md`
- `docs/superpowers/plans/2026-07-27-stylecapture-journey.md`

进入完整 P0 开发前必须先通过 M0 付费问题门（7 天招募/统一报价，加旅行后成熟观察）；未通过时修订或停止该楔子，不用功能堆叠掩盖需求证据不足。

---

# Legacy demo route — archived reference only

以下内容是原抖音 Feed/H5 评审演示的历史计划，只用于理解已有资产来源。它不适用于
StyleCapture Journey，不得作为该独立 App 的 scope、实现顺序、mock 策略、真人试穿要求或
完成标准。Journey 执行只以上述商业路线文档和 active Goal 为准。

## 一、历史产品定义（文档/PPT 按此结构写：痛点 → 能力 → 实现）

  

### 1.1 两个核心痛点（独立拆分）

  

|   |   |   |
|---|---|---|
|痛点|本质|对应产品能力|
|P1：不知道自己有哪些衣服 / 收藏了哪些|**资产沉淀**问题|数字衣橱：三类来源（自有上传 / 电商添加 / 推荐流圈选）统一拆解入库、打标|
|P2：不知道怎么搭配 / 种草新衣不知道能不能和已有的搭|**搭配决策**问题|AI 搭配引擎：衣橱优先配齐 → 配不齐推电商单品 → 全套购买链接|

  

### 1.2 种草决策场景（导师认可的核心链路）

  

用户在抖音种草一件新衣时纠结三件事：①我是不是已经有相似的了？②它能不能和我已有的衣服搭？③符不符合我的风格？

→ 产品回答：识别新衣 + 比对衣橱 → 给出风格匹配度 + 已有搭配方案；配不齐 → 推荐适配单品 + 全套购买链接。

  

### 1.3 三个触发场景

  

1. **场景/风格输入**："周五面试穿什么" → 衣橱内出 3–4 套方案
    
2. **目标单品查询**：种草未购的单品 → 和自有衣橱的搭配效果 + 购买决策建议
    
3. **feed 流圈选**：暂停圈选目标衣物 → 弹出卡片展示"该单品 × 你的衣橱"搭配效果
    

### 1.4 收益叙事（PPT 用，导师给的三维度）

  

① 电商导流交易（衣橱偏好数据回传 + 缺失单品推荐 + 一键配齐）

② 用户资产沉淀 → 抖音留存与活跃

③ 像素分享卡的社交传播性

  

### 1.5 展示方案（已定）

  

- 缩略层：像素小人（bonus，延后）
    
- 详情页：**左侧各单品真实图 + 购买链接，右侧 AI 生成真人全套穿搭效果图**
    
- 每次搭配请求输出 3–4 套方案
    
- 分享时一键生成像素风版本（bonus）
    

---

  

## 二、数据模型（三个实体，开发前先定稿）

  

```JavaScript
// Item —— 单品（核心实体，衣橱的原子单位）
{
  id: string,
  name: string,                    // "米色风衣"
  category: '上衣'|'下装'|'鞋'|'外套'|'配饰',
  colors: string[],
  styleTags: string[],             // ["法式","通勤"]
  sceneTags: string[],             // ["面试","约会"]
  source: 'own' | 'collected' | 'ecommerce',  // 自有上传 / 圈选收藏 / 电商添加
  originalImageUrl: string,        // 真实图（核心展示用）
  bbox: [x,y,w,h] | null,          // 提取时的框
  searchQuery: string,             // 电商搜索词
  buyLink: string,
  pixelUrl: string | null          // bonus，延后生成
}

// OutfitPlan —— 搭配方案（AI 生成或用户收藏的整套）
{
  id: string,
  scene: string,                   // "面试"
  wardrobeItemIds: string[],       // 来自衣橱的单品
  recommendedItems: Item[],        // 电商补全的单品（衣橱配不齐时）
  isFullyFromWardrobe: boolean,    // ← "满足判断"分支结果
  rationale: string,               // 搭配逻辑说明（评委要看的"标注搭配逻辑"）
  styleMatchScore: number,         // 风格匹配度（种草决策场景用）
  tryOnImageUrl: string | null,    // AI 真人效果图
  pixelCardUrl: string | null      // 像素分享卡，bonus
}

// UserProfile
{
  height, weight, sizes,           // 注册时采集，用于真人效果图
  photoRefUrl: string | null,      // 用户参考照（可选）
  stylePreference: string[]        // 由 collected 类 Item 加权计算得出
}
```

  

**权重规则**：计算"已有资产"时 own > collected；计算"风格偏好"时 collected 权重更高（收藏代表向往的风格，自有代表现状）。

  

---

  

## 三、模块拆分与分工（4 个可独立开发模块 + 1 个统筹）

  

### 模块 A｜入库基建：流量引入 → 衣物拆解 → 入库（1 人）

  

- **职责**：三类来源统一走一条提取链路——截图/照片/圈选帧 → VLM 一次调用返回整套描述 + 各单品结构化 JSON（category/colors/styleTags/sceneTags/searchQuery/bbox）→ 标注 source → 入库
    
- **交付 API**：
    
    - `POST /api/items/ingest` （imageBase64 + source）→ `Item[]`
        
    - `GET /api/wardrobe` → `{ items: Item[], profile: UserProfile }`
        
- **复用**：改造现有 `/api/outfits/enrich`（百炼识图已通），state.js 存储层
    
- **降级**：VLM 失败 → 预置识别结果（mockData 已有机制）
    

### 模块 B｜搭配引擎：AI Workflow（1 人）

  

- **职责**：核心决策逻辑。输入衣橱 JSON + 用户请求（场景/风格 或 目标单品），输出 3–4 套 `OutfitPlan`
    
- **内部流程**（这就是评审要的 AI 链路）：
    
    - 需求理解：解析场景/风格/目标单品
        
    - 衣橱优先：从自有+收藏单品中组合配齐
        
    - **满足判断分支**：`isFullyFromWardrobe`？是 → 出方案；否 → 生成缺失品类的 searchQuery → 电商单品推荐 + 一键配齐链接
        
    - 每套方案附 rationale（搭配逻辑）+ styleMatchScore
        
- **交付 API**：`POST /api/match` （wardrobe + request）→ `OutfitPlan[]`
    
- **复用**：`/api/chat` LLM 代理、searchQuery→淘宝/京东链接生成
    
- **关键**：与模块 A 只通过 Item schema 耦合，**开发期用 mock 衣橱数据即可并行**
    

### 模块 C｜真人效果图生成（1 人，可与 B 同人兼任）

  

- **职责**：输入 OutfitPlan（单品图集合）+ UserProfile（身材/参考照）→ 生图 API 输出真人全套穿搭效果图
    
- **交付 API**：`POST /api/render/tryon` → imageUrl
    
- **Demo 策略**（导师原话"大力出奇迹"）：演示用的 3–4 套方案**提前预生成**存本地，现场调用只是兜底；生图失败降级为单品拼贴图
    
- **画风稳定性**：真实画风只用于效果图这一处，prompt 固定模板 + 固定人物参考，不追求任意输入稳定
    
- **bonus（主线跑通后）**：像素分享卡生成（复用初赛 pixel-avatar 链路）
    

### 模块 D｜前端展示（1–2 人）

  

改造现有 H5，页面清单按依赖排序：

  

1. **衣橱页**（改现有图鉴页）：单品网格用真实图、来源筛选 tab、上传入口（拍照/相册 → 模块 A）
    
2. **搭配请求页**：场景/风格输入 → 方案卡列表（3–4 套）→「换一套」
    
3. **方案详情页**：左单品真实图+购买链接列 / 右真人效果图；「一键配齐」聚合页
    
4. **feed 流页**（改现有模拟流）：暂停 → 单品框（bbox 渲染）→ 圈选 → 弹卡片"该单品 × 你的衣橱"
    
5. **注册页**：身材信息采集（身高/体重/尺码，可跳过）
    
6. bonus：像素小人缩略、分享卡
    

**开发期全部页面对着 mock JSON 写**（Phase 0 定稿的契约），不等后端。

  

### 模块 E｜统筹：部署 / 文档 / PPT（Lion 兼任）

  

- 文档按"痛点 → 能力 → 实现"结构重写（导师明确要求，不要按链路顺序写）
    
- 收益三维度叙事
    
- 部署（现有 node server 上公网）
    
- Skill 包：**部署完成后**再写（把 A+B 的 workflow 写成 SKILL.md 打包）
    
- 备份演示视频
    

---

  

## 四、开发顺序：哪里串行、哪里并行

  

```Plain
Phase 0（全员，~1.5h，唯一必须串行的环节）
  ├── 定稿三个实体 schema + 4 个 API 签名 + 写好 mock JSON 文件（demo 衣橱 15–20 件单品）
  │   ⚠️ 此后 schema 冻结，改动需全员同意
  └── 代码仓库整理（白板任务 4）：清理初赛遗留分支/死代码，按模块 A–D 划分目录归属，
      main 保护、各模块独立分支开发，避免四路并行时互相踩踏

Phase 1（四路并行，互不阻塞）
  ├── A：ingest 真链路（VLM prompt → 结构化 JSON + bbox）
  ├── B：match 引擎（用 mock 衣橱开发 prompt 与分支逻辑）
  ├── C：tryon 生图调通 + 用 mock 方案预生成 demo 效果图
  └── D：全部页面对 mock 开发

Phase 2（两两集成，有先后依赖）
  ├── ① A→B：真实入库数据喂给搭配引擎（最先联调，核心链路）
  ├── ② B→C：真实方案生成效果图
  └── ③ D 接全部真接口（最后，替换 mock 为 fetch）

Phase 3（收尾，串行）
  └── 部署上线 → 按 demo 主线走查×3 → 修阻断 bug → 录备份视频 → 文档/PPT 定稿 → Skill 包

Bonus 窗口（仅当 Phase 2 提前完成）：像素分享卡 → 像素小人缩略 → 捏脸
```

  

**时间刻度（按 40h 窗口）**：Phase 0 ≈ 开工后 1.5h 内；Phase 1 ≈ 至 T+16h；Phase 2 ≈ T+16–26h；Phase 3 ≈ T+26–36h；最后 4h 纯 buffer。若进度落后，砍序不砍链：先砍 bonus，再砍注册页（身材写死默认值），再砍 feed 流圈选（用相册上传演示入库）——**A→B→C→D 的"场景→方案→效果图→购买"主链不可砍**。

  

**关键路径**：A 的提取质量决定 B 的推荐质量，B 的方案决定 C 的效果图——A 是第一优先级；D 完全不在关键路径上，可从头到尾并行。

  

---

  

## 五、Demo 主线（评委体验路径，对应两个痛点）

  

```Plain
① 注册：填身高体重（或跳过）
② 【痛点1 资产沉淀】拍照上传 3 件自有衣物 → 自动拆解打标入库
③ 【痛点1】刷 feed 流 → 暂停圈选种草外套 → 弹卡片："和你衣橱里的白衬衫、
   牛仔裤可以这样搭，风格匹配度 87%" → 收藏入库
④ 【痛点2 搭配决策】搭配请求："周五面试" → 3–4 套方案卡
⑤ 点进方案：左侧单品真实图 + 右侧真人穿搭效果图 + 搭配逻辑说明
⑥ 【电商出口】其中一套提示"你还缺一双乐福鞋" → 推荐单品 → 一键配齐购买清单
⑦ 【bonus 社交出口】一键生成像素分享卡
```

  

---

  

## 六、v1 → v2 变更记录

  

|   |   |   |   |
|---|---|---|---|
|项|v1|v2|原因|
|叙事主线|视觉搜索闭环|痛点驱动（资产沉淀+搭配决策）|导师：视觉搜索是手段不是卖点|
|核心画风|像素风为主|真实画风为主，像素风=分享 bonus|导师：像素损失细节伤害核心价值|
|满足判断|用户 👍/👎 反馈|AI 内部分支（衣橱配齐 or 电商补全）|团队复盘：应交给 workflow 判断|
|语音输入|P1 建议挤进主线|砍掉|视觉已足够，多模态非必要|
|Skill 包|与部署同期|部署后再做|先定型产品 loop|
|像素小人|P0 主线|bonus 延后|优先跑通真人搭配链路|
|数据实体|Outfit{items[]} 两层|Item / OutfitPlan / UserProfile 三实体|单品升格为原子单位；方案与收藏分离|
