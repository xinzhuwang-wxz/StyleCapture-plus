# Promptfoo 离线评测基线（Product API Smoke）

本目录不新增线上运行时依赖，也不引入 Docker 镜像；仅通过离线 CLI（固定版本）从
Product API 路径执行能力 smoke。

- 评测目标：`outfit.scene_matching`（`POST /v1/outfit-plans`）
- 评测入口：仅走 Product API（Session + `/v1/outfit-plans` + Trace 查询）
- 提示词治理与模型决策不在此处实现，模型/模型 ID 与 provider 只在后端配置与适配器
  中存在，符合 `ADR-0005`。

## 文件

- `promptfoo.yaml`：离线 smoke 用例与参数。
- `providers/stylecapture-product-api.mjs`：用于 Product API 的自定义 provider。

## 前置条件

1. 本地服务可用：`/v1/session` 与 `/v1/outfit-plans` 可达。
2. 有可用的演示/测试会话上下文（如 `demo_wardrobe` 已开启）。
3. Node.js >= 20（Promptfoo 与 `fetch` 语义一致）。

## 运行方式（固定版本）

```bash
# 建议显式版本，避免本地解析漂移
PROMPTFOO_VERSION=0.121.19
npx --yes "promptfoo@${PROMPTFOO_VERSION}" eval -c evals/promptfoo/promptfoo.yaml
```

或在单独进程固定版本（CI/脚本）：

```bash
STYLECAPTURE_API_URL=http://127.0.0.1:8000 \
  npx --yes "promptfoo@0.121.19" eval -c evals/promptfoo/promptfoo.yaml
```

可选：若希望复用已建立的会话，先置入 `STYLECAPTURE_SESSION_COOKIE`。

本机 Node 版本不满足 Promptfoo 要求时，复用现有 Compose 网络运行一次性容器；这不会
给产品镜像增加依赖，也不会使用宿主机不稳定的 `host.docker.internal` 解析：

```bash
docker run --rm \
  --network stylecapture_default \
  --cpus=1.5 --memory=2g \
  -v stylecapture-promptfoo-npm-cache:/root/.npm \
  -v "$PWD:/workspace" -w /workspace \
  -e STYLECAPTURE_API_URL=http://api:8000 \
  node:22.22-alpine \
  sh -lc 'npx --yes promptfoo@0.121.19 eval -c evals/promptfoo/promptfoo.yaml --max-concurrency 1 --no-cache'
```

## 为什么这样定义“Smoke”

- 覆盖 3 个正向场景（不同 scene/style/formality/comfort/weather 组合）。
- 覆盖 1 个负向场景（必填场景缺失，应返回 `request_invalid`）。
- 每个正向场景都要求：
  - 能返回可查询 trace 的 `request_id/trace_id`
  - trace 可读取且返回 step 列表
  - trace 不回漏 `prompt/media/provider` 等基础设施字段
  - 产出至少 1 个方案

该 baseline 适合放在轻量 CI 或 PR 冒烟窗口；完整覆盖另行放在 full 评测集。
