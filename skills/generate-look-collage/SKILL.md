---
name: generate-look-collage
description: 为 StyleCapture 的穿搭详情页生成或重试真实单品拼贴图，要求纯白背景、平衡 flat-lay 构图、所有单品完整可见且不裁切。适用于“穿搭拼贴图不好看”“真实拼贴”“collage”“look board”或需要让单品拼贴更美观时。
---

# 穿搭真实单品拼贴

执行前先读取 [拼贴构图规范](references/collage-composition.md)。这个 Skill 只负责整套穿搭详情页的 `collage` 图，不负责单品详情页的 3:4 白底图，也不负责按单品瀑布流的像素卡。

借鉴旧 Wardrobe `generate-outfits` workflow 的原则：每件真实衣物都要保持原样、完整、可识别；构图要有主次和呼吸空间；不要为了“像一套搭配”而改造、补画或遮挡真实单品。

## 工作流

1. 读取 `GET /v1/looks/{look_id}`，确认 Look 中至少有 1 个、最多 8 个已就绪 `Item`。
2. 优先使用每个 Item 当前可用的真实白底图或 display asset；不要从人物原图里重新裁剪，也不要把像素卡放进拼贴。
3. 请求或重试 `POST /v1/looks/{look_id}/renders`，`kind` 使用 `collage`。
4. 轮询 `GET /v1/looks/{look_id}/renders`，直到当前 `collage` 为 `succeeded` 或 `failed`。
5. 如果生成失败或画面被裁切，修复源图/布局后重新排队，不要把失败图发布到穿搭详情页。

## 关键验收

- 画面是 3:4 竖版 PNG，背景为干净白色或透明白底。
- 所有单品完整出现在画面内，任何衣摆、鞋尖、包带、项链链条都不能贴边或被裁掉。
- 最多两件视觉面积最大的衣物作为主视觉；其他鞋包、袜子、首饰、腰带等小件进入右侧或下方的紧凑分区。
- 主单品不能独占整张图；小件不能漂到边角。整体应像商品搭配 flat-lay，而不是随机散落截图。
- 不包含人物、皮肤、场景、UI 文案、按钮、标签、水印、边框或额外装饰。

## 使用

```bash
STYLECAPTURE_API_URL=http://127.0.0.1:8000 \
node scripts/render-look-collage.js --look-id "<look UUID>" --wait
```

如果本地没有脚本，直接通过 Product API 触发同一个 `collage` render；后端确定性渲染器是最终真源。
