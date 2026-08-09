---
name: pixel-character-card
description: 将真实人物照、穿搭照或半身照转换为稳定的竖版 3:4 全身像素小人卡片。适用于需要保留人物发型、表情、眼镜、动态姿势、服装版型、鞋履和配饰，同时用与穿搭气质相符的轻量卡片背景替换原场景的任务。
---

# 像素小人卡片

本 Skill 是 StyleCapture Product API 的薄客户端。它负责上传用户图片、提交像素卡任务、等待结果并下载成图；固定画风、正面参考图、提示词版本、3:4 尺寸、随机种子和模型路由全部由服务端统一管理。不要在 Skill 内复制生成提示词，也不要直接调用模型供应商或 LiteLLM。

## 工作流

1. 确认输入是一张含单个人物的 JPG、PNG、WebP、HEIC 或 HEIF 图片。全身照优先；半身照也可提交，由服务端补全自然协调的下装与鞋履。
2. 读取 [references/style-contract.md](references/style-contract.md)，明确正面标准与反面边界。不要把用户原背景当作必须复刻的场景。
3. 调用脚本：

```bash
python scripts/generate_pixel_card.py /absolute/path/to/photo.jpg \
  --output /absolute/path/to/pixel-card.png
```

4. 脚本通过 Product API 创建私人会话、上传原图、提交异步任务并轮询，成功后保存图片。接口细节见 [references/api-contract.md](references/api-contract.md)。
5. 对照风格合同检查：画布必须为竖版 3:4、单人全身、头顶和鞋底完整、脚下有轻量地毯；人物外轮廓为明显粗方格像素，脸部、头发和服装内部保持精致层次；保留原图的主导姿势，禁止把抬手、伸臂、侧身、坐姿等动态动作改成双臂垂下的僵直立正；背景不能空白，也不能复刻复杂原场景；没有明确场景标志物时只用简单抽象点缀，禁止把服装、鞋、包或首饰复制成漂浮装饰。
6. 如果生成失败，报告脚本输出的错误码和可重试状态。不要在本地另写一套提示词绕过 Product API。

## 参数

- `--api-base-url`：覆盖 `STYLECAPTURE_API_URL`。默认使用已部署的 StyleCapture 服务。
- `--output`：成图保存路径；默认写到输入图片旁边的 `*-pixel-card.png`。
- `--timeout-seconds`：整个上传与异步生成流程的上限，默认 180 秒。
- `--poll-seconds`：轮询间隔，默认 2 秒。
- `STYLECAPTURE_SESSION_COOKIE`：可选，复用已有私人会话；未设置时由 Product API 新建会话。

## 输出约束

成功时脚本向标准输出写一行 JSON，包含 `status`、`trial_id`、`output` 和 `elapsed_seconds`，不包含供应商密钥、内部模型 ID 或原图字节。图片内容质量以 [references/style-contract.md](references/style-contract.md) 为准。
