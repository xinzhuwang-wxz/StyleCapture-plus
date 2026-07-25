# Prompt Design

## 目录

- [边界](#边界)
- [系统提示](#系统提示)
- [用户消息](#用户消息)
- [输出 schema](#输出-schema)
- [Few-shot](#few-shot)
- [失败处理](#失败处理)

## 边界

模型只负责：

1. 在确定性代码生成的候选中排序。
2. 为候选改写简洁、具体的搭配逻辑。
3. 输出 0–100 的风格匹配分。

模型不得新增、删除或替换单品，不得生成库存、价格或购买事实。脚本在接受结果前重新检查候选 plan id、数量、分数和解释。

## 系统提示

```text
你是穿搭审美重排器。只能重排给定候选并改写解释，不能添加、删除或替换单品。
返回严格 JSON：
{"rankedPlans":[{"id":string,"rationale":string,"styleMatchScore":0..100}]}。

要求：
1. rankedPlans 必须包含 3–4 个互不重复的候选 id。
2. id 必须来自输入 candidates。
3. rationale 必须解释配色、层次、场景或目标单品关系，不写空泛夸奖。
4. styleMatchScore 必须是 0–100 的数字。
5. 不输出 Markdown、代码围栏、库存、价格或不存在的商品事实。
```

## 用户消息

把以下对象序列化为 JSON 字符串作为 user message：

```json
{
  "request": {
    "scene": "周五面试",
    "style": "",
    "question": "",
    "targetItem": null
  },
  "candidates": [
    {
      "id": "plan-a83c1095115a",
      "scene": "周五面试",
      "wardrobeItemIds": [
        "own-white-shirt",
        "own-navy-trousers",
        "own-navy-blazer",
        "own-black-tote"
      ],
      "recommendedItems": [
        {
          "id": "commerce-search-b336d2663a08",
          "category": "鞋",
          "searchQuery": "周五面试 黑色通勤乐福鞋",
          "buyLink": "https://search.jd.com/Search?keyword=周五面试%20黑色通勤乐福鞋"
        }
      ],
      "isFullyFromWardrobe": false,
      "rationale": "确定性规则生成的候选解释。",
      "styleMatchScore": 88
    }
  ]
}
```

生产调用传递完整候选对象；上例仅缩短了展示。

## 输出 schema

```json
{
  "type": "object",
  "required": ["rankedPlans"],
  "properties": {
    "rankedPlans": {
      "type": "array",
      "minItems": 3,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["id", "rationale", "styleMatchScore"],
        "properties": {
          "id": {"type": "string"},
          "rationale": {"type": "string", "minLength": 8},
          "styleMatchScore": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
          }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

## Few-shot

### 输入：场景

```json
{
  "request": {"scene": "周五面试", "style": "", "question": "", "targetItem": null},
  "candidates": [
    {"id": "plan-1", "wardrobeItemIds": ["white-shirt", "navy-trousers", "navy-blazer"], "recommendedItems": [{"category": "鞋", "searchQuery": "黑色通勤乐福鞋"}]},
    {"id": "plan-2", "wardrobeItemIds": ["black-dress", "grey-coat"], "recommendedItems": [{"category": "鞋", "searchQuery": "低跟通勤鞋"}]},
    {"id": "plan-3", "wardrobeItemIds": ["ivory-blouse", "black-skirt"], "recommendedItems": [{"category": "鞋", "searchQuery": "法式芭蕾鞋"}]}
  ]
}
```

### 输出

```json
{
  "rankedPlans": [
    {
      "id": "plan-1",
      "rationale": "白衬衫与藏蓝套装形成清晰、可信赖的面试基调，黑色乐福鞋补足正式度。",
      "styleMatchScore": 94
    },
    {
      "id": "plan-3",
      "rationale": "象牙白与黑色构成克制对比，过膝裙和低调鞋型兼顾专业感与法式线条。",
      "styleMatchScore": 90
    },
    {
      "id": "plan-2",
      "rationale": "黑色连衣裙减少层次冲突，浅灰大衣提亮整体，适合偏正式且天气较冷的面试。",
      "styleMatchScore": 87
    }
  ]
}
```

### 输入：目标单品

```json
{
  "request": {
    "scene": "",
    "style": "",
    "question": "这件未购外套能不能和我的衣橱搭？",
    "targetItem": {
      "id": "target-red-trench",
      "name": "酒红色短款风衣",
      "category": "外套"
    }
  },
  "candidates": [
    {"id": "plan-a", "wardrobeItemIds": ["ivory-blouse", "navy-trousers"], "recommendedItems": [{"id": "target-red-trench"}]},
    {"id": "plan-b", "wardrobeItemIds": ["black-knit", "black-skirt"], "recommendedItems": [{"id": "target-red-trench"}]},
    {"id": "plan-c", "wardrobeItemIds": ["striped-knit", "blue-jeans"], "recommendedItems": [{"id": "target-red-trench"}]}
  ]
}
```

### 输出

```json
{
  "rankedPlans": [
    {
      "id": "plan-a",
      "rationale": "酒红风衣与象牙白上衣形成柔和明暗层次，藏蓝西裤稳定通勤正式度。",
      "styleMatchScore": 93
    },
    {
      "id": "plan-b",
      "rationale": "全黑内搭让酒红风衣成为视觉中心，轮廓简洁且适合晚间通勤或约会。",
      "styleMatchScore": 89
    },
    {
      "id": "plan-c",
      "rationale": "条纹针织和牛仔裤降低风衣的正式感，适合更松弛的法式日常搭配。",
      "styleMatchScore": 85
    }
  ]
}
```

## 失败处理

以下任一情况拒绝模型结果并使用确定性候选：

- 请求超过 15000ms。
- HTTP 非 2xx。
- 内容不是 JSON。
- `rankedPlans` 数量不在 3–4。
- id 不属于候选或重复。
- rationale 为空。
- `styleMatchScore` 越界。

降级必须设置 `degraded: true` 并记录机器可读原因；不要伪造模型成功。
