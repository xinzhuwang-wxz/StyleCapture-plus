# Issue #84：AI 单品详情图纯白背景

**Issue:** https://github.com/xinzhuwang-wxz/StyleCapture-plus/issues/84

## 目标

新生成的 `flat_lay_item` 保持 1728×2304 和真实单品质感，但 AI 路径不得再发布带灰斑、纸张纹理、渐变或投影的背景；主体外背景统一为数字纯白 `#FFFFFF`。

## 实现范围

- 强化 Seedream 文本约束，明确背景只能是平坦 `#FFFFFF`，禁止米白、灰白、纹理、污点、渐变和所有阴影。
- 仅对 AI 输出执行确定性背景清理：用非背景轮廓形成保护屏障、填充被轮廓包围的浅色商品内部，再只把商品蒙版外强制纯白。
- 保留保护框内的浅色、白色和金属主体像素；透明 `refined_mask` 的 Pillow 路径保持不变。
- 升级 flat-lay 签名和 schema，避免新请求复用旧的灰斑资产。
- 同步 Skill 与输出契约，增加灰斑清理和浅色主体保护回归测试。

## 复用审计

| 能力 | 候选 | 决策 | 原因 | 来源 / 许可 |
|---|---|---|---|---|
| 图像生成 | 现有 LiteLLM `image_generation` / Seedream 适配器 | 直接复用 | 不新增第二套 provider 链路，仅收紧提示与验收 | 本仓库；LiteLLM MIT |
| 背景处理 | 现有 Pillow、`_near_white_mask`、`ImageDraw.floodfill` 模式 | 适配复用 | 已在同模块处理像素卡连通背景，无需引入 rembg 或重型分割模型 | 本仓库；Pillow HPND |
| 精细透明抠图 | 现有 `refined_mask` + `PillowLookCollageRenderer` | 直接复用 | 已能产生真正纯白画布，不改变成熟路径 | 本仓库 |
| 二次模型审查 | VLM/再次生图 | 拒绝 | 增加时延和成本；确定性清理与质量门槛足以覆盖当前灰斑缺陷 | 不适用 |

## 验证

- [x] 灰斑背景回归测试先失败，再由最小实现修复。
- [x] 浅色金属/白色主体保护测试通过。
- [x] AI prompt、signature、schema 和 provider trace 测试通过。
- [x] Item presentation 测试、Ruff、mypy、Skill 校验和脚本测试通过。
- [x] 推送分支并创建 PR #85，附 Issue 与验证结果。

## 视觉证据

- `docs/evidence/flat-lay-white-background-regression-v2.png`：左侧为近白脏底、灰斑和近白衣物输入，右侧为同一算法输出；灰斑被清除，近白面料、浅灰轮廓与棕色细节保留。
- 该图是确定性后处理回归证据，不冒充真实 provider 输出；真实缺陷来自用户在产品中的新上传结果截图。

## 意外与发现

- 旧版 `normalize_flat_lay_image` 会把全图所有 RGB 通道均不低于 248 的像素直接改白。这不仅清背景，也会删除白衣的布料层次，是用户截图中白色上装和下装几乎消失的直接原因。
- 纯色阈值不能承担商品分割职责。最终实现改为用较深/有色轮廓形成保护屏障并填充被包围的浅色内部，再只清理蒙版外区域。

## 决策记录

- 2026-08-10：只对 AI 路径启用更强背景清理；透明精细抠图继续使用原 Pillow 合成，避免对已正确的 alpha 主体重复推断。
- 2026-08-10：删除对整张图片所有近白像素的全局漂白。中心商品保护区内保留原像素，只清理框外背景，避免银饰、白衣与浅色鞋被洗掉。
