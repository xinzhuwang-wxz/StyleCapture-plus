---
name: real-photo-flat-lay-collage
description: 通过 StyleCapture Product API，将已抓取并保存为 Look 的真实人物穿搭照或服装照片转为纯白 3:4 的真实单品平铺拼贴图。适用于需要从已处理的真实照片生成可查看、可重试且受会话保护的服饰拆分展示图时。
---

# 真实照片平铺拼贴

本 Skill 是 StyleCapture `collage` RenderArtifact 的薄客户端。它不直接处理本地图片、
不维护服饰识别或抠图规则，也不调用模型、Provider 或 Prompt。所有真实图像与单品
事实均以 Product API 的 Capture、Item 和 Look 为唯一真源。

## 工作流

1. 先通过正常的 Feed/上传抓取流程保存一张用户有权使用的真实人物穿搭照或衣物照，等待它形成一个至少含有已就绪单品的 `Look`。
2. 用此 Skill 向 `POST /v1/looks/{look_id}/renders` 请求 `{ "kind": "collage" }`，并始终提供新的 `Idempotency-Key`。
3. 轮询 `GET /v1/render-artifacts/{artifact_id}`，直到状态为 `succeeded`、`failed` 或 `degraded`；成功后只使用 API 返回的私有 `output_image_url` 读取图片。
4. 将结果称为“真实单品拼贴”，而不是新的服装事实或 AI 试穿。单品来源、权限、缓存、任务状态、失败重试和私有图片访问全部继续由产品后端管理。

## 输出约束

`collage` 的默认渲染必须使用已就绪的真实 Item 展示资产生成一张确定性的 PNG：竖版 **3:4**、纯白背景、正视/平铺的独立单品、明确留白和一致的轻微接触阴影。它不得保留人物、皮肤、场景、镜面、手机、字幕或水印；不得生成新的单品、品牌文字或像素画。

若上游没有把真实照片成功保存为可用 Look，或 Look 没有可用的 Item 展示资产，直接返回 Product API 的错误或失败状态；不得用固定图片、浏览器拼接或猜测出的服装补位。

## 使用

先启动核心服务，然后执行：

```bash
STYLECAPTURE_API_URL=http://127.0.0.1:8000 \
node scripts/render.js --look-id "<look UUID>" --wait
```

可选参数：

- `--api-base-url`：覆盖 `STYLECAPTURE_API_URL`。
- `--session-cookie`：复用当前私人会话；未提供时创建产品会话。
- `--wait`：等待异步渲染完成并输出最终 Artifact。
- `--timeout-ms`：等待上限，默认 90 秒，最大 180 秒。

## 与产品流程的关系

```text
真实图片抓取 → Capture → 单品识别/展示资产 → Look（单品就绪）
→ 本 Skill 请求 collage → RenderArtifact 队列 → Pillow 纯白 3:4 拼贴
→ 私有 Artifact 图片 → H5 Look 详情页
```

Skill 仅覆盖箭头中“请求 collage 并读取结果”的部分。H5、Worker 和外部调用方复用同一套版本化 API，禁止将本 Skill 中的客户端逻辑变成第二套业务流程。

运行验证：

```bash
npm test
```
