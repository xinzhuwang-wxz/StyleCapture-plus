# Issue #64：单品像素卡视觉修复

**Issue:** https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/64

## 目标

让 `按单品` 双列瀑布流的 1:1 像素卡符合已确认的 StyleCapture 收藏卡语言：主体完整、背景柔和但不统一灰白，中央没有黑灰光圈，四角具有阶梯双线层次，每张卡只保留 4–7 个固定但不镜像的小装饰。

## 用户可见结果

- `pixel_item` 仍输出 1024×1024 PNG，只用于单品缩略卡。
- 豆包只生成近白背景上的像素单品主体，不生成光圈、投影、边框或装饰。
- 后端在 256×256 逻辑网格合成高明度外底、无模糊中心色块、阶梯双线四角和 6 个固定非对称小装饰，再用最近邻放大。
- 不向豆包传入额外风格参考图片；上传图或 Item 图只作为单品内容输入。
- 不新增额外模型审美检查或二次生成调用。
- 3:4 `flat_lay_item` 详情图链路保持不变。

## 复用审计

| 能力 | 候选 | 决策 | 原因 | 来源 / 许可证 |
|---|---|---|---|---|
| Item 像素任务与私有资产 | 现有 `item_presentation` 状态、签名、Worker 与对象存储 | 直接复用 | 已拥有幂等、重试、权限和发布边界，不新增第二条业务链路 | 本仓库 |
| 像素主体生成 | 现有 `LiteLLMImageGenerator` / `image_generation` alias | 适配复用 | 仅收紧文字提示，仍从服务器端统一网关调用真实 Seedream | 本仓库；LiteLLM MIT |
| 卡面绘制 | 现有 Pillow 后处理 | 适配复用 | 256 逻辑网格、背景分离与最近邻放大已存在；删除错误高斯合成并替换装饰模板即可 | 本仓库；Pillow HPND |
| 风格锚点 | 用户提供的三张正面单品卡 | 仅人工视觉评审 | 用户明确要求本轮不给豆包风格参考图；将视觉特征转成文字和确定性模板 | 用户会话素材，不作为运行时输入 |
| 审美自动检查 | 第二次 VLM / 生图评估 | 本轮拒绝 | 会增加调用成本和等待时间，且用户明确要求先不加 | 不适用 |

## 进度

- [x] 定位黑圈来自高斯椭圆合成与后处理，而非产品必要阴影。
- [x] 定位普通 L 角与镜像装饰来自硬编码绘图函数。
- [x] 改为纯文字风格提示、干净主体输出和确定性卡面合成。
- [x] 增加阶梯双线四角与固定非对称装饰。
- [x] 用三件真实 Seedream 单品串行验证上衣、裙装与白鞋。
- [x] 完成目标后端测试、静态检查、Skill 校验与本地 H5 启动检查。
- [x] 创建 PR #65 并附上真实生成证据。

## 真实证据

- 输入：已有真实单品内容图；未发送任何额外风格参考图。
- 模型：`doubao-seedream-5-0-260128`，三次串行调用。
- 结果：三张 provider 原图均为近白底、无装饰像素主体；最终卡片通过现有基础尺寸与浅色边缘门槛。
- 视觉证据：`docs/evidence/pixel-item-ornate-v3.png`。

## 验证

- `pytest services/backend/tests/item_presentation -q` → 11 passed。
- `ruff check services/backend/src/stylecapture_backend/features/item_presentation services/backend/tests/item_presentation` → passed。
- `mypy` 检查 Item presentation application 与 processing → passed。
- Skill Creator `quick_validate.py skills/generate-outfit-item-assets` → valid。
- `node --test skills/generate-outfit-item-assets/tests/render.test.js` → 2 passed。
- H5 在 `127.0.0.1:5174` 成功启动；当前本地会话无 Item 数据，未用 mock 冒充真实单品页面证据。

## 决策记录

- 2026-08-09：删除高斯模糊中央光晕，使用无模糊、低对比的实心中心色块，避免透明黑边参与 RGB 合成。
- 2026-08-09：卡框和装饰由后端模板负责；模型提示明确禁止自行生成这些元素，避免双重构图。
- 2026-08-09：保留多套高明度背景色，但统一使用同一种阶梯边框与非镜像装饰语法。
- 2026-08-09：本轮不增加额外模型质量检查；继续保留低成本的解码、尺寸和浅色安全边验证。
- 2026-08-09：装饰数量从 16 个收敛为 6 个（允许范围 4–7 个），并升级像素资产签名与卡面 schema，避免旧缓存继续返回装饰过多的版本。
