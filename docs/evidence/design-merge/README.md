# Design Merge — 走查证据

分支 `codex/design-merge-gaps`。全部在 390×844 视口下由
`apps/h5/e2e/design-merge-gaps.spec.ts` 产出，运行方式：

```
STYLECAPTURE_E2E_BASE_URL=http://127.0.0.1:5199 \
  pnpm --dir apps/h5 exec playwright test e2e/design-merge-gaps.spec.ts
```

结果：**4 passed, 1 skipped**（跳过的那条见下方「没验证到的部分」）。

## 身材信息定制

| 截图 | 内容 |
|---|---|
| `01-profile-before-metrics.png` | 默认态，摘要提示「补全身材数据」 |
| `02-body-metrics-sheet.png` | 六个滚轮，范围与设计稿一致 |
| `03-body-metrics-saved.png` | 保存后摘要显示身高与身型 |
| `04-body-metrics-after-refresh.png` | **刷新后仍在**——不只是 React state |
| `05-body-metrics-recovered-from-corruption.png` | **失败态与恢复态**：手工把存档写成非法 JSON 后重新加载，应用照常启动并回落到默认值 |

改动走的是键盘路径（`ArrowUp`），因为滚轮同时声明成 `spinbutton`——
读屏用户实际拿到的就是这条路。`body-metrics.json` 记录了当次选中的值。

## 形象照管理

| 截图 | 内容 |
|---|---|
| `06-photo-manager-empty.png` | 空相册 |
| `07-photo-rejected-non-image.png` | **失败态**：传 `.txt` 被挡下并说明原因 |
| `08-photo-accepted-after-rejection.png` | **恢复态**：紧接着传真图片仍能进去 |
| `09-photo-persisted-after-refresh.png` | 刷新后 `localStorage` 里确实是 `data:image/` |

## 组合衣柜

| 截图 | 内容 |
|---|---|
| `10-wardrobe-items-with-combo-buttons.png` | 每张卡片都有「加入组合衣柜」按钮 |
| `11-combo-basket-one-item.png` | 放入一件 |
| `12-combo-basket-two-items.png` | 放入两件，可保存 |
| `13-combo-conflict-reported.png` | **失败态**：两条连衣裙，提示「选了 2 条连衣裙」，保存按钮置灰 |
| `14-combo-conflict-cleared.png` | **恢复态**：移出一件后提示消失，保存重新可用 |

`combo-basket.md` 记录了这条链路**全程没有触发任何指针拖拽**——只点按钮。
拖拽是增强，这份证据证明它不是唯一入口。

### 走查抓到的一个真缺陷

`12-combo-basket-two-items.png` 第一次跑出来时，篮子里的缩略图全是灰块：
`basketEntryOf` 取的是 `display_image_url`，而种子单品只有 `pixel_image_url`。
卡片本身用的是后者。已改成与卡片同源（含相同的 `?v=` 版本号），并补了
`tests/combo-basket.test.ts` 的回归测试。上表截图是修复后重跑的。

## 没验证到的部分（分享图鉴）

`share-sheet-not-reached.md`。衣橱里 9 套穿搭没有一套带 `share_eligible`
的像素封面——`demo_assets/seed-manifest.json` 里 `pixel_cover` 出现 0 次，
要生成得跑真实 AI 链路。分享入口按设计就不出现，所以这条真机链路**没有走到**。

测试因此显式 `skip`，而不是点第一套发现没有就当作「跳过」并报绿。
覆盖这块的是 `tests/share-card-sheet.test.tsx` 的 8 个单测。
这不是「验证过」，是「没验证到」。

## 自动化基线

- `pnpm --dir apps/h5 test` → 27 files / 217 tests 通过
- `pnpm --dir apps/h5 typecheck` → 干净
- `pnpm --dir apps/h5 build` → 成功

已知既有 flake：`tests/app.test.tsx` 的「removes a restored processing card」
在满载并行下偶发找不到「正在理解这件衣服」，单独跑与重跑都绿，成因是计时，
早于本分支。没有为它放宽断言。
