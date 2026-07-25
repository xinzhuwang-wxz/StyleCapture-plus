---
name: scene-outfit-matching
description: 通过 StyleCapture Product API，从用户真实数字衣橱生成场景穿搭方案。
---

# 场景搭配

本技能只是 Product API 的薄客户端。它不读取第二份衣橱 JSON，不维护分类、
召回、搭配规则或模型提示，也不直接调用 LiteLLM。衣橱资产、规则降级、AI 重排、
保存票据和错误语义均以服务端 `/v1/outfit-plans` 合同为唯一真源。

## 使用

先启动 StyleCapture 核心服务，然后执行：

```bash
STYLECAPTURE_API_URL=http://127.0.0.1:8000 \
node scripts/match.js \
  --request '{"scene":"周五面试","style":"简洁正式"}'
```

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
