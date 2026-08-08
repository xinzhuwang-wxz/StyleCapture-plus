---
name: real-photo-flat-lay-collage
description: 通过 StyleCapture Product API，将新抓取的视频截图或上传穿搭图中的每个真实 Item 直接生成纯白 3:4 独立单品图。适用于新穿搭拆分完成后创建、轮询或重试单品详情页大图；不依赖整套拼贴图，也不从拼贴图裁剪单品。
---

# 真实穿搭独立单品图

把 Product API 作为 Capture、Look、Item、任务状态和私有图片权限的唯一真源。不要在 Skill 客户端复制识别、抠图、模型选择或存储逻辑。

## 工作流

1. 通过 Feed 截图或上传流程保存一张用户有权使用的穿搭图，等待后端形成含已就绪 Item 的 `Look`。
2. 读取 `GET /v1/looks/{look_id}`，收集不重复的 `components[].item_id`。
3. 为每个 Item 请求 `POST /v1/items/{item_id}/presentations/flat-lay`；需要结果时轮询 `GET /v1/item-presentations/{asset_id}` 至 `succeeded` 或 `failed`。
4. 将成功的 `output_image_url` 用作单品详情页大图。生成中继续显示虚化原图和“正在生成单品图”；失败时保留原图，不得显示空白详情页。

不要先请求整套 `collage`，也不要从整套拼贴图二次裁剪单品。

## 后端生成规则

- 只有带 `refined_mask` 元数据且具有有效透明通道的精细抠图，才允许用 Pillow 放入 1728×2304 白色画布。
- 矩形截图、粗多边形、无透明通道、抠图缺失或不合格时，直接使用原始穿搭图和 Item 属性调用配置的图像生成能力。
- 两条路径都必须通过相同质量门槛：精确 3:4、1728×2304、边缘近白比例至少 90%、纯白区域至少 50%、四角为 `#FFFFFF`。
- 单图只包含所属单品；鞋可成对。禁止人物、皮肤、场景、手机、其他衣物、文字、品牌、水印、灰色矩形底、裁切和拉伸。
- 重叠位置要先判断肩带、腰头、系带、纽扣和装饰分别属于哪件衣物，不得把其他 Item 的部件转移到目标单品；遮挡处只允许按目标单品可见材质做保守连续补全。
- 质量门槛失败时进入可重试失败状态，不得把不合格图片发布到详情页。

新 Capture 完成 Item 识别后自动排队。不要批量回填历史 Item；旧 Item 只有在产品明确请求其 `flat-lay` presentation 时才按现有 API 处理。

## 使用

```bash
STYLECAPTURE_API_URL=http://127.0.0.1:8000 \
node scripts/render.js --look-id "<look UUID>" --wait
```

可选参数：

- `--api-base-url`：覆盖 `STYLECAPTURE_API_URL`。
- `--session-cookie`：复用当前私人会话；未提供时创建产品会话。
- `--wait`：等待每个 Item 的异步任务完成。
- `--timeout-ms`：等待上限，默认 90 秒，最大 180 秒。

```text
视频截图/上传图 → Capture → Look 与 Item 识别
→ 每个 Item 直接创建 flat_lay_item
→ 精细透明抠图走 Pillow，否则走图像生成
→ 统一质量门槛 → 单品详情页 3:4 白底大图
```

运行验证：

```bash
npm test
```
