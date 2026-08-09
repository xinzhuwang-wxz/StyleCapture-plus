---
name: scene-outfit-matching
description: 通过 StyleCapture Product API，从用户真实数字衣橱生成场景穿搭方案。
---

# 场景搭配

本技能只是 Product API 的薄客户端。它不读取第二份衣橱 JSON，不维护分类、
召回、搭配规则或模型提示，也不直接调用 LiteLLM。衣橱资产、规则降级、AI 重排、
保存票据和错误语义均以服务端 `/v1/outfit-plans` 合同为唯一真源。

## 推荐约束

- 请求可通过 `outfit_count` 选择 3 或 4 套方案，未传时默认 4 套。
- 方案只能引用 Product API 返回的真实衣橱单品；缺口必须保留为明确的搜索需求。
- 候选需要兼顾同色或邻近色协调、受控撞色、视觉重量、廓形平衡和合理叠穿。
- 多套方案应尽量分散复用衣物，并保持结构或真实单品组合唯一。
- Skill 只传递条件和展示结果，数量校验、召回、硬规则与 LiteLLM 重排均由服务端负责。

## 使用

下载后可直接调用已部署的 StyleCapture Product API：

```bash
node scripts/match.js \
  --request '{"scene":"周五面试","style":"简洁正式","outfit_count":3}'
```

默认服务为 `https://119.45.216.38`。本地开发或迁移部署时，可通过
`STYLECAPTURE_API_URL` 或 `--api-base-url` 覆盖，不需要修改 Skill 代码。

可选传入：

- `--api-base-url`：覆盖 `STYLECAPTURE_API_URL`。
- `--timeout-ms`：端到端等待上限，默认 90 秒，最大 180 秒。
- `STYLECAPTURE_SESSION_COOKIE`：复用已有私人衣橱会话；未设置时由服务端创建会话。

输出保留版本化 Product API 的 `OutfitPlanSetResponse`，并使用返回的 `trace_id`
查询 `/v1/outfit-plans/traces/{trace_id}`，将经过身份与合同校验的结果附在
`workflow_trace`。Skill 不自行编造追踪记录，也不输出模型提示、媒体内容或 provider
细节；前端、Worker 和其他调用方均应复用 OpenAPI 生成合同。

运行验证：

```bash
npm test
```
