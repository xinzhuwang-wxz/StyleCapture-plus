# Sandbox

- 仅修改 `codex/pr12-main-integration`，不直接改 PR #12/#10 的远端分支。
- 真实托管 LiteLLM 与 light worker 可用；不等待 GPU，不在笔记本运行重型批处理。
- E2E `workers=1`，长任务前后检查 CPU、内存、swap、磁盘与 Docker。
- 只复用现有 Product API、对象存储、任务与渲染边界；禁止引入第二套业务合同或大依赖。
- 发现当前生命周期内的 P0/P1 当轮修复；独立可选项才允许另建 Issue。

