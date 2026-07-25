# PR12 移动端全生命周期 AutoResearch Mission

## 目标

在 `codex/pr12-main-integration` 上完成至少三轮真实移动端研究循环，并继续到一整轮多角色
审查不再发现新 P0/P1；最终使普通新用户、评委、
产品/交互、前端、后端/数据库与 AI 真链路视角均无未解决 P0/P1。功能不仅正确，还应在
390×844 的首次使用中清楚、连续、可恢复、无英文业务文案、无假结果。

## 必测生命周期

1. Feed 浏览、暂停、恢复、常亮圈选、手势引导、多次圈选、单品/整套入库与来源回看。
2. 相机/相册上传、单品/整套确认、真实理解、去背景实物图、像素一级展示、详情真源、
   歧义照片说明、原图删除与恢复语义。
3. 中文需求到逐套 AI 推荐、保存 Look、真实拼贴、真人试穿、像素封面、购买状态。
4. 独立全身照像素 Try：真实生成、不入库、失败可重试。
5. 前端状态、Product API、异步任务、PostgreSQL/Object Store 事实一致。

## 验收门槛

- 至少三轮 AutoResearch 均有独立 `experiment:` 提交、机械验证、截图和结果记录；若第三轮
  仍发现新 P0/P1，则继续循环，直到下一整轮审查无新问题。
- Backend Ruff/Mypy/Pytest、H5 Vitest/typecheck/build、OpenAPI、Promptfoo 与目标 E2E 通过。
- 多角色审查不依赖同一审查者自证；架构验证者给出 `approved`。
- 没有运行时 mock/stub/fixed result、curated seed 冒充 AI、provider/key 泄漏或跨层合同漂移。
- 主机资源处于 `LOCAL-RESOURCE-GUARDRAILS.md` 安全范围。
