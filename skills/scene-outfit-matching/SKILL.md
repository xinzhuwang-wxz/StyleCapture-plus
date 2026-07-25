---
name: scene-outfit-matching
description: 根据用户数字衣橱与目标场景、风格或种草单品生成 3–4 套结构化搭配方案，并在衣橱缺少必要单品时给出诚实的电商搜索补全建议。当用户询问某场景穿什么、某风格怎么搭，或某件未购衣物能否与已有衣物搭配时使用。
---

# 场景搭配

## 何时使用

在以下任一意图出现时使用：

- 场景搭配，例如“周五面试穿什么”。
- 风格搭配，例如“法式通勤怎么搭”。
- 目标单品决策，例如“这件未购风衣能不能和我的衣橱搭”。

示例请求：

```json
{"scene":"周五面试"}
```

不要用本技能声称库存、价格或同款关系。`recommendedItems` 只表示缺失品类的搜索需求。

## 输入格式

准备一个衣橱 JSON 文件。顶层可以是 `Item[]`，也可以是包含 `items` 的对象。每个 Item 至少提供：

```json
{
  "id": "own-white-shirt",
  "name": "白色挺括衬衫",
  "category": "上衣",
  "colors": ["白色"],
  "styleTags": ["通勤", "极简"],
  "sceneTags": ["面试"],
  "source": "own",
  "originalImageUrl": "https://example.invalid/wardrobe/white-shirt.jpg",
  "bbox": null,
  "searchQuery": "",
  "buyLink": "",
  "pixelUrl": null
}
```

请求必须使用下列一种形式：

```json
{"scene":"周五面试"}
```

```json
{"style":"法式通勤"}
```

```json
{
  "targetItem": {
    "imageDescription": "一件酒红色短款风衣，翻领，适合通勤",
    "category": "外套",
    "colors": ["酒红"],
    "styleTags": ["法式", "通勤"]
  },
  "question": "这件未购外套能不能和我的衣橱搭？"
}
```

目标单品可以是完整结构化 Item，也可以是上面的图片描述形式；缺少 ID、搜索词
和购买链接时，入口会生成稳定 ID 与通用搜索链接，不会虚构商品库存或价格。

读取完整字段、枚举和输出约束时，查看 [references/schema.md](references/schema.md)。

## 调用方式

从技能目录执行：

```bash
node scripts/match.js \
  --wardrobe assets/mock-wardrobe.json \
  --request '{"scene":"周五面试"}' \
  --no-llm
```

连接 LiteLLM `reasoning` 能力时设置服务端环境变量：

```bash
export STYLECAPTURE_LITELLM_URL="http://127.0.0.1:4000"
export STYLECAPTURE_LITELLM_API_KEY="replace-with-server-key"
node scripts/match.js \
  --wardrobe assets/mock-wardrobe.json \
  --request '{"style":"法式通勤"}'
```

也可以显式传入 `--llm-base-url` 和 `--timeout-ms`；密钥仍必须来自环境变量。超时始终被限制在 15000ms 以内。不要把密钥写进命令行、仓库、fixture、日志或输出。

### 交互式 Playground

需要让用户通过页面试用或验收三种触发方式时，从技能目录启动：

```bash
npm run playground
```

然后打开 `http://127.0.0.1:4174`。页面直接调用同一份 `matchOutfits` 逻辑，
可以切换场景、风格和目标单品，查看衣橱引用、缺失补全、匹配分数、降级状态及
完整 JSON。默认关闭 LiteLLM，便于离线验证确定性降级；打开开关时从既有环境
变量读取 LiteLLM 配置。此页面仅是本地人工验收工具，不代表正式 H5 的产品设计、
交互规范或生产部署边界。

## 输出格式

输出一个 JSON 对象，其中 `outfitPlans` 始终包含 3–4 套方案：

```json
{
  "schemaVersion": "scene-outfit-matching.v1",
  "requestId": "运行时生成的 UUID",
  "triggerType": "scene",
  "degraded": true,
  "degradationReason": "llm_disabled",
  "outfitPlans": [
    {
      "id": "plan-e6e60c8fb6ea",
      "scene": "周五面试",
      "wardrobeItemIds": [
        "own-ivory-blouse",
        "own-beige-trousers",
        "own-grey-coat",
        "own-black-tote"
      ],
      "recommendedItems": [
        {
          "id": "commerce-search-cbe0731e78e8",
          "name": "黑色通勤乐福鞋（搜索推荐）",
          "category": "鞋",
          "colors": [],
          "styleTags": [],
          "sceneTags": ["周五面试"],
          "source": "ecommerce",
          "originalImageUrl": null,
          "bbox": null,
          "searchQuery": "周五面试 黑色通勤乐福鞋",
          "buyLink": "https://search.jd.com/Search?keyword=%E5%91%A8%E4%BA%94%E9%9D%A2%E8%AF%95%20%E9%BB%91%E8%89%B2%E9%80%9A%E5%8B%A4%E4%B9%90%E7%A6%8F%E9%9E%8B",
          "pixelUrl": null
        }
      ],
      "isFullyFromWardrobe": false,
      "rationale": "周五面试：以象牙白真丝衬衫、米色直筒西裤、浅灰羊毛大衣、黑色结构感托特包建立主色与层次，兼顾场景正式度和风格一致性。衣橱暂缺鞋，已给出明确搜索需求。",
      "styleMatchScore": 85,
      "tryOnImageUrl": null,
      "pixelCardUrl": null
    }
  ]
}
```

把 `isFullyFromWardrobe` 视为分支事实：只有 `recommendedItems` 为空时才为 `true`。下游可以直接把 `wardrobeItemIds` 交给衣橱服务，把 `recommendedItems` 交给购买补全或效果图模块。

## 决策流程

按以下顺序执行：

1. 识别 `scene`、`style` 或 `targetItem` 触发类型。
2. 优先选择 `own`，其次选择 `collected`。
3. 用确定性槽位模板生成不同的上衣/下装或连衣裙组合。
4. 对缺失槽位生成 `ecommerce` 搜索需求；不要生成库存和价格。
5. 将封闭候选集交给 LiteLLM `reasoning` 重排和改写解释。
6. 验证模型只能返回候选 plan id，且分数和解释符合 schema。
7. 输出 3–4 套方案。

需要审查完整模型提示和 few-shot 时，查看 [references/prompt-design.md](references/prompt-design.md)。

## 降级行为

当 LiteLLM 未配置、超时、HTTP 失败、返回非法 JSON 或引用未知 plan id 时：

1. 保留确定性衣橱优先方案。
2. 设置 `degraded: true`。
3. 在 `degradationReason` 中输出机器可读原因，例如 `llm_timeout`。
4. 保留真实 `recommendedItems` 搜索需求，不把降级描述成模型成功。

降级示例：

```json
{
  "degraded": true,
  "degradationReason": "llm_timeout"
}
```

运行完整验证：

```bash
npm test
```
