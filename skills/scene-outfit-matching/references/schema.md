# Scene Outfit Matching JSON Schema

## 目录

- [输入](#输入)
- [输出](#输出)
- [字段语义](#字段语义)

## 输入

### Wardrobe

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://stylecapture.example/schemas/scene-outfit-wardrobe.v1.json",
  "oneOf": [
    {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/$defs/Item"}
    },
    {
      "type": "object",
      "required": ["items"],
      "properties": {
        "items": {
          "type": "array",
          "minItems": 1,
          "items": {"$ref": "#/$defs/Item"}
        }
      },
      "additionalProperties": true
    }
  ],
  "$defs": {
    "Item": {
      "type": "object",
      "required": [
        "id",
        "name",
        "category",
        "colors",
        "styleTags",
        "sceneTags",
        "source"
      ],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "category": {
          "enum": ["上衣", "下装", "连衣裙", "外套", "鞋", "配饰"]
        },
        "colors": {"type": "array", "items": {"type": "string"}},
        "styleTags": {"type": "array", "items": {"type": "string"}},
        "sceneTags": {"type": "array", "items": {"type": "string"}},
        "source": {"enum": ["own", "collected", "ecommerce"]},
        "originalImageUrl": {"type": ["string", "null"]},
        "bbox": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "array",
              "prefixItems": [
                {"type": "number"},
                {"type": "number"},
                {"type": "number"},
                {"type": "number"}
              ],
              "minItems": 4,
              "maxItems": 4
            }
          ]
        },
        "searchQuery": {"type": "string"},
        "buyLink": {"type": "string"},
        "pixelUrl": {"type": ["string", "null"]}
      },
      "additionalProperties": false
    }
  }
}
```

### MatchRequest

请求至少提供一种触发结构；如果同时提供 `targetItem`，以目标单品触发为准。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://stylecapture.example/schemas/scene-outfit-request.v1.json",
  "type": "object",
  "properties": {
    "scene": {"type": "string", "minLength": 1},
    "style": {"type": "string", "minLength": 1},
    "targetItem": {"$ref": "#/$defs/TargetItemInput"},
    "question": {"type": "string"}
  },
  "anyOf": [
    {"required": ["scene"]},
    {"required": ["style"]},
    {"required": ["targetItem"]}
  ],
  "additionalProperties": false,
  "$defs": {
    "TargetItemInput": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "imageDescription": {"type": "string"},
        "category": {
          "enum": ["上衣", "下装", "连衣裙", "外套", "鞋", "配饰"]
        },
        "colors": {"type": "array", "items": {"type": "string"}},
        "styleTags": {"type": "array", "items": {"type": "string"}},
        "sceneTags": {"type": "array", "items": {"type": "string"}},
        "originalImageUrl": {"type": ["string", "null"]},
        "bbox": {
          "type": ["array", "null"],
          "items": {"type": "number"},
          "minItems": 4,
          "maxItems": 4
        },
        "searchQuery": {"type": "string"},
        "buyLink": {"type": "string"},
        "pixelUrl": {"type": ["string", "null"]}
      },
      "anyOf": [
        {"required": ["name"]},
        {"required": ["description"]},
        {"required": ["imageDescription"]}
      ],
      "additionalProperties": false
    }
  }
}
```

`targetItem` 可以使用完整结构化 Item，也可以只提供图片描述。缺少 `id`、
`searchQuery` 或 `buyLink` 时，入口会分别生成稳定 ID、以描述为搜索词，并补充
HTTPS 搜索链接；不会虚构具体商品库存或价格。若未给 `category`，入口只在描述
含有可识别品类词时推断，否则明确拒绝输入。

## 输出

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://stylecapture.example/schemas/scene-outfit-response.v1.json",
  "type": "object",
  "required": [
    "schemaVersion",
    "requestId",
    "triggerType",
    "degraded",
    "degradationReason",
    "outfitPlans"
  ],
  "properties": {
    "schemaVersion": {"const": "scene-outfit-matching.v1"},
    "requestId": {"type": "string", "minLength": 1},
    "triggerType": {"enum": ["scene", "style", "target_item"]},
    "degraded": {"type": "boolean"},
    "degradationReason": {"type": ["string", "null"]},
    "outfitPlans": {
      "type": "array",
      "minItems": 3,
      "maxItems": 4,
      "items": {"$ref": "#/$defs/OutfitPlan"}
    }
  },
  "additionalProperties": false,
  "$defs": {
    "RecommendedItem": {
      "type": "object",
      "required": [
        "id",
        "name",
        "category",
        "colors",
        "styleTags",
        "sceneTags",
        "source",
        "originalImageUrl",
        "bbox",
        "searchQuery",
        "buyLink",
        "pixelUrl"
      ],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "category": {
          "enum": ["上衣", "下装", "连衣裙", "外套", "鞋", "配饰"]
        },
        "colors": {"type": "array", "items": {"type": "string"}},
        "styleTags": {"type": "array", "items": {"type": "string"}},
        "sceneTags": {"type": "array", "items": {"type": "string"}},
        "source": {"const": "ecommerce"},
        "originalImageUrl": {"type": ["string", "null"]},
        "bbox": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "array",
              "prefixItems": [
                {"type": "number"},
                {"type": "number"},
                {"type": "number"},
                {"type": "number"}
              ],
              "minItems": 4,
              "maxItems": 4
            }
          ]
        },
        "searchQuery": {"type": "string", "minLength": 1},
        "buyLink": {"type": "string", "pattern": "^https://"},
        "pixelUrl": {"type": ["string", "null"]}
      },
      "additionalProperties": false
    },
    "OutfitPlan": {
      "type": "object",
      "required": [
        "id",
        "scene",
        "wardrobeItemIds",
        "recommendedItems",
        "isFullyFromWardrobe",
        "rationale",
        "styleMatchScore",
        "tryOnImageUrl",
        "pixelCardUrl"
      ],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "scene": {"type": "string", "minLength": 1},
        "wardrobeItemIds": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "recommendedItems": {
          "type": "array",
          "items": {"$ref": "#/$defs/RecommendedItem"}
        },
        "isFullyFromWardrobe": {"type": "boolean"},
        "rationale": {"type": "string", "minLength": 8},
        "styleMatchScore": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        },
        "tryOnImageUrl": {"type": "null"},
        "pixelCardUrl": {"type": "null"}
      },
      "additionalProperties": false
    }
  }
}
```

## 字段语义

| 字段 | 语义 |
|---|---|
| `wardrobeItemIds` | 当前衣橱真实 Item 引用，不复制 Item 事实。 |
| `recommendedItems` | 目标未购单品或缺失槽位的电商搜索需求；不代表真实库存、价格或同款。 |
| `isFullyFromWardrobe` | 当且仅当 `recommendedItems` 为空时为 `true`。 |
| `rationale` | 对当前真实组合的搭配逻辑说明。 |
| `styleMatchScore` | 0–100 的相对风格匹配分，不表示购买概率。 |
| `degraded` | 未使用有效 LLM 重排时为 `true`。 |
| `degradationReason` | `llm_disabled`、`llm_not_configured`、`llm_timeout` 或具体校验错误。 |
| `tryOnImageUrl` | Issue #5 渲染前固定为 `null`。 |
| `pixelCardUrl` | Bonus 像素卡生成前固定为 `null`。 |
