# `_ref` 复用资料清单

`_ref` 只保存需要审计、适配或验证的参考源码，不作为产品运行时源码目录。正式实现必须把需要的能力通过清晰接口接入主工程，不能直接跨目录依赖 `_ref`。

## 采用原则

- 能通过稳定包或托管 API 使用的能力，锁版本和接口，不复制整仓源码。
- 需要改造、封装 GPU Worker 或迁移现有产品能力的项目，保留源码快照。
- 复用项目的内部数据模型不能直接成为产品真源；统一转换为本项目的 `Capture / Item / Look / OutfitPlan / RenderArtifact` 合同。
- 不把模型权重、生成结果、用户图片和依赖缓存提交到主仓库。
- 测试可使用 fake provider；运行时和现场演示不能用 mock/stub 冒充真实 AI 结果。

## 本地已有产品源码

| 项目 | 定位 | 复用方式 |
|---|---|---|
| `video-branch-main` | 已复刻的抖音 Feed、React/Vite H5、FastAPI、共享合同、Agent/Skill、Playground、trace 与部署骨架 | 作为主工程骨架；保留 Feed 视觉与滚动/暂停行为，改造现有锚点交互为服装圈选和入库任务 |
| `StyleCapture-main` | 数字衣橱原型、紫粉像素视觉、角色和图标资产、衣橱/详情/识别页面、像素生成 provider router | 迁移数字衣橱体验和像素资产；保留视觉语言与信息架构，不保留全局状态和旧式内联页面组织 |

## 已选开源源码

| 项目 | 固定版本 | 许可证 | 采用级别 | 负责能力 |
|---|---:|---|---|---|
| [`wardrowbe`](https://github.com/Anyesh/wardrowbe) | `c63ced9` | MIT | 适配复用 | 衣物/套装数据模型、异步打标任务、AI provider 边界、迁移与测试模式 |
| [`sam2`](https://github.com/facebookresearch/sam2) | `2b90b9f` | Apache-2.0 | 直接封装 | 用户圈选后的图像分割、视频掩码细化和短时传播 |
| [`Grounded-SAM-2`](https://github.com/IDEA-Research/Grounded-SAM-2) | `b7a9c29` | Apache-2.0 | 适配复用 | 开放词汇服装候选检测与 SAM2 组合范式；只取集成方式，不复制其内置 SAM2 副本 |
| [`product-taxonomy`](https://github.com/Shopify/product-taxonomy) | `574be7a` | MIT | 数据复用 | 服装品类、属性和值的基础词表；本地为服饰与中文本地化的稀疏检出 |
| [`marqo-FashionCLIP`](https://github.com/marqo-ai/marqo-FashionCLIP) | `d0b3bdf` | Apache-2.0 | 模型/评测复用 | 服装领域图文向量与相似检索；运行时从 Hugging Face 加载 FashionSigLIP，不复制模型实现 |
| [`FastFit`](https://github.com/Zheng-Chong/FastFit) | `9c96fc0` | Non-Commercial | Demo 条件采用 | 多参考上衣、下装、连衣装、鞋、包的整套真人试穿；必须部署在隔离 GPU Worker |
| [`fashn-vton-1.5`](https://github.com/fashn-AI/fashn-vton-1.5) | `7c0f10a` | Apache-2.0 | 直接封装 | 单件上衣/下装/连衣装试穿与 FastFit 的质量/故障回退 |

## 作为依赖或服务使用，不下载整仓

| 能力 | 选择 | 原因 |
|---|---|---|
| 视频抽帧 | FFmpeg | 成熟系统工具，保留精确时间戳；不手写解码 |
| 镜头检测 | PySceneDetect | 仅在需要补充上下文帧时调用；不是主链路硬依赖 |
| 多模态理解 | 火山方舟可配置视觉模型；Qwen3-VL 为开源/自托管备选 | 使用 OpenAI-compatible provider 接口，避免业务代码绑定模型名 |
| 向量存储 | PostgreSQL + pgvector | 与资产事务、权限和过滤条件同库，当前规模不引入第二套向量数据库 |
| 后台任务 | Redis + Celery | 成熟的重试、dead-letter 和并发控制；复用 `wardrowbe` 的任务状态思想，不复用 arq 运行时 |
| 对象存储 | S3-compatible 接口；当前部署映射到腾讯 COS | 源图、帧、mask、单品图、试穿图和像素图统一存储 |
| GPU 执行 | 单台 48 GB GPU 主机上的锁版本推理容器 | 一台机器覆盖分割、向量和试穿；Redis/Celery 将重任务串行，容器隔离 CUDA/Python 依赖 |
| 前端服务状态 | TanStack Query | 避免手写请求缓存、重试和轮询 |
| 交互动画 | Motion + SVG/Canvas | 圈选拖尾、主体浮起与直接横滑复用成熟动画原语，不引入 3D 引擎 |

## 明确不采用

- 不把 `wardrowbe` 的 Next.js 前端并入产品；数字衣橱必须保持 `StyleCapture-main` 的视觉。
- 不把旧 Polyvore 推荐仓库作为线上推荐引擎；仅用相关数据和论文做离线评测参考。
- 不用 Qdrant/Elasticsearch 再建一套索引；首版使用 pgvector。
- 不把 ComfyUI 作为业务编排层；GPU Worker 直接调用固定、可测试的推理 pipeline。
- 不在 P0/P1 实现 3D 服装网格、布料仿真或 SMPL-X 数字人。ECON、4D-DRESS 等仅保留未来研究结论，不下载到本地。
- 不复制 FastFit 自带的 Gradio UI、detectron2 配置树或未固定依赖；只封装推理入口并构建独立锁版本镜像。

## 协同边界

1. Feed 只产生 `Capture` 与用户选择，不等待 AI 打标结果。
2. 入库服务先持久化 Capture/Look/Item 占位记录，再把分割、拆件、打标和向量化交给后台任务。
3. 所有视觉模型输出必须经过本项目 schema 校验、taxonomy 归一化和置信度门控。
4. Wardrobe、搭配 Skill、H5 和 Playground 读取同一套 API 与数据库，不各自维护一份业务规则。
5. 试穿和像素图都是 `RenderArtifact`，可重试、可缓存、可替换，永远不是 Item/Look 的事实真源。
6. FastFit 的非商业许可证只允许当前非商业 Demo；商业化前必须替换或取得授权。
7. 所有复用能力必须收敛到版本化领域 API；H5、Skill、Worker 和外部调用方不能直接依赖第三方项目的数据表或内部函数。
