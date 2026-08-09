---
name: generate-outfit-item-assets
description: 通过 StyleCapture Product API，为新抓取的视频截图或上传穿搭图中的每个真实 Item 同时生成纯白 3:4 详情图与统一的 1:1 像素收藏卡。适用于新穿搭拆分完成后创建、轮询或重试单品详情页大图和“按单品”双列缩略图；不依赖整套拼贴图，也不从拼贴图裁剪单品。
---

# 真实穿搭 Item 双资产

执行前先读取 [输出与界面映射](references/output-contract.md)。它规定两张图片各自出现的位置，以及图片中绝对不能包含的前端 UI 元素。

把 Product API 作为 Capture、Look、Item、任务状态和私有图片权限的唯一真源。不要在 Skill 客户端复制识别、抠图、模型选择或存储逻辑。

## 工作流

1. 通过 Feed 截图或上传流程保存一张用户有权使用的穿搭图，等待后端形成含已就绪 Item 的 `Look`。
2. 读取 `GET /v1/looks/{look_id}`，收集不重复的 `components[].item_id`。
3. 为每个 Item 分别请求 `POST /v1/items/{item_id}/presentations/pixel` 与 `POST /v1/items/{item_id}/presentations/flat-lay`；需要结果时轮询 `GET /v1/item-presentations/{asset_id}` 至 `succeeded` 或 `failed`。
4. 将成功的 `flat_lay_item.output_image_url` 用作单品详情页大图。生成中继续显示虚化原图和“正在生成单品图”；失败时保留原图，不得显示空白详情页。
5. 将成功的 `pixel_item.output_image_url` 用作 `按单品 → 双列瀑布流` 的 1:1 缩略卡。生成中显示彩色像素占位图和状态，不得把 3:4 详情图裁成方形替代。

不要先请求整套 `collage`，也不要从整套拼贴图二次裁剪单品。

## 3:4 详情图规则

- 只有带 `refined_mask` 元数据且具有有效透明通道的精细抠图，才允许用 Pillow 放入 1728×2304 白色画布。
- 矩形截图、粗多边形、无透明通道、抠图缺失或不合格时，直接使用原始穿搭图和 Item 属性调用配置的图像生成能力。
- 两条路径都必须通过相同质量门槛：精确 3:4、1728×2304、边缘近白比例至少 90%、纯白区域至少 50%、四角为 `#FFFFFF`。
- 单图只包含所属单品；鞋可成对。禁止人物、皮肤、场景、手机、其他衣物、文字、品牌、水印、灰色矩形底、裁切和拉伸。
- 重叠位置要先判断肩带、腰头、系带、纽扣和装饰分别属于哪件衣物，不得把其他 Item 的部件转移到目标单品；遮挡处只允许按目标单品可见材质做保守连续补全。
- 质量门槛失败时进入可重试失败状态，不得把不合格图片发布到详情页。

## 1:1 像素卡规则

生成前读取 [像素单品卡视觉规范](references/pixel-item-card-style.md)。

- 严格请求正方形图片，后端统一输出 1024×1024 PNG；不得依赖前端 CSS 裁切修正比例。
- 只保留一个目标单品，正面居中且完整可见。鞋保留一双；明确成组的配饰才允许整组出现。
- 主体使用统一硬边 16-bit / 32-bit 商品像素画：深一档同色描边、有限色阶、像素块大小一致；禁止半写实半像素、模糊、平滑抗锯齿、3D 和照片质感。
- 为每个 Item 从蜜桃、丁香紫、晴空蓝、薄荷绿、奶油黄和莓果粉中稳定选择一种协调色板；不同 Item 应形成柔和变化，不得整批默认成灰白底。模型生成对应色相和中央光晕，后端重着色边缘连通背景并叠加统一边框、星光和爱心。
- 后端固定执行 256×256 像素网格、96 色无抖动量化，再用最近邻放大到 1024×1024。
- 发布前必须通过 1:1 尺寸和浅色安全边质量门槛。失败时保留彩色内置像素图标，不得回退为人物截图或 3:4 白底图。

新 Capture 完成 Item 识别后，两种资产自动排队。不要批量回填历史 Item；旧 Item 只有在产品明确请求对应 presentation 时才按现有 API 处理。

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
→ 每个 Item 直接创建 pixel_item + flat_lay_item
→ pixel_item → 稳定多色色板 + 统一像素网格与装饰模板 → 按单品 1:1 缩略卡
→ flat_lay_item → 精细透明抠图走 Pillow，否则走图像生成
→ 单品详情页 3:4 白底大图
```

运行验证：

```bash
npm test
```
