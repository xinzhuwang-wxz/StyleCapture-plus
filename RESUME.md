# 续接笔记（更新于 2026-07-27 下午）

完整方案与目标契约见 `/Users/yuxingtianxia/.claude/plans/main-main-main-main-html-main-main-use-logical-corbato.md`。
这份只记「现在停在哪、下一步做什么」。

## 重要变化：Stage 6 已经不需要做了

PR #36 的头分支就是 `codex/issue-9-community-dance-demo`——也就是那两个所谓
「孤儿 commit」的来源。它在 **2026-07-27T02:15:31Z 已被合并进 main**，
合并点 `8c0e506`。核对过 main 的实际内容：7 位角色、7 套 pose 立绘、
在场名单、`recordClip` 录像、`scripts/pixel_sprite.py`、`pixel_look_cutout.py`
全都在，`gifenc` 引用为 0。

我在过期基点上手工重放了一遍（commit `4713df9`、`3c1b89a`），是重复劳动。
这两个 commit 已经从交付线上摘掉，但**没有删**，仍在旧分支
`codex/design-merge` 上（`3c1b89a`）留档。

**目标契约 Done #2 已经满足，只是不由我完成。**

## 当前分支

- 交付分支：**`codex/design-merge-gaps`**，基于 `db0bb18`，只含 Stage 1–5。
- 旧分支 `codex/design-merge` 保留在 `3c1b89a`，仅作留档，不要用它开 PR。

| commit | 内容 |
|---|---|
| `ac38587` | 本地持久化底座 `src/storage/localStore.ts` |
| `9157d0f` | 身材信息定制 `features/profile/`（MetricWheel + BodyProfileSheet） |
| `98c1f75` | 形象照管理 PhotoManagerSheet（最多 6 张，只收 `data:image/`） |
| `d6ef99b` | 组合衣柜 `features/combo/` + litellm 的 `cryptography<47` 约束 |
| `db0bb18` | 分享图鉴 `features/outfit/ShareCardSheet.tsx` |

验证：`pnpm test` 216/216、`typecheck` 干净、`build` 成功。

## Stage 7 已完成

PR **#42** 已开：https://github.com/xinzhuwang-wxz/StyleCapture-plus/pull/42
核对过实际状态：`OPEN` / `MERGEABLE` / `mergeState: CLEAN` / CI `product` 通过（2m49s）。
跟 `f7abb615` 的新 main 没有冲突，不需要 rebase。

下一轮是用户说的「统一视觉风格设计」——换皮，独立开一轮。

<details><summary>原 Stage 7 清单（已做完）</summary>


1. **分支落后于 main**：本地 `origin/main` 是 `b1b08ab`，远端 main 已到 `f7abb615`
   （多了 PR #36 和 #40）。我这条分支基于 `b1b08ab`。开 PR 后要用
   `gh pr view --json mergeable` 看会不会冲突；大概率的冲突点是 `App.tsx`。
   真要 rebase 就需要 `git fetch`，而当前约束禁止——到时候要请用户定夺。
2. 删掉被取代的代码；确认 `e2e/community-ballroom.spec.ts` 在新 main 上是否还有效
   （PR #36 可能已经处理过了，先查再动）。
3. 更新 ExecPlan。
4. 390×844 真机走完整条链路留证据，**含失败态与恢复态**：Feed 圈选 → 衣橱 →
   穿搭详情 → AI 推荐 → 分析 → 我的（身材/形象照）→ 组合衣柜 → 分享弹层。
5. 本地持久化单独验证：写入 → 刷新 → 读回；手工写坏 localStorage 后仍能启动。
6. 开 PR，然后**用 `gh pr view` 核对实际状态**，不要把推送当作「PR 已更新」。

## 环境状态

- 这个会话里 Bash 开始被权限分类器拦截：`git reset --hard`、`ls`、`git ls-files`
  都被拒了。继续之前可能需要用户在设置里放开 Bash 权限规则。

## 已知的坑（别重新踩）

- **`tests/app.test.tsx` 的「removes a restored processing card」在满载并行下偶发失败**
  （找不到「正在理解这件衣服」）。单独跑、重跑都绿，是计时敏感的既有 flake。
  别为它改断言。
- 网络操作只用 `gh` CLI。禁止 `git fetch/pull/push/ls-remote`、`gh repo clone`。
- 不碰 `/Users/yuxingtianxia/Documents/StyleCapture-plus`（另一个 Agent 的 PR #12）。
- 不改现有类名和可见文案——十几个既有测试断言依赖它们。
- macOS 大小写不敏感：`ComboBasket.tsx` 和 `comboBasket.ts` 会撞，逻辑模块已改名
  `basketRules.ts`。
- litellm 在本机 arm64 上需要 `pyproject.toml` 的
  `constraint-dependencies = ["cryptography<47"]`，否则 SIGILL。
- ARK key 只在 gitignored `.env` 里，不进 commit / 截图 / 日志。已建议用户轮换。

## 用户的下一轮

「这个做完之后再统一视觉风格设计」——换皮是独立的下一轮，本轮**只补功能**。

</details>
