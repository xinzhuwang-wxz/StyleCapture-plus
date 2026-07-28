# StyleCapture-plus

StyleCapture-plus 是可自托管的 AI 数字衣橱。默认运行方式是轻量 Docker
Compose 核心栈：H5、FastAPI、PostgreSQL/pgvector、Redis、Worker 和 LiteLLM。
本地默认不加载 GPU 模型；视觉理解、搭配推理和生图由你选择的托管 API 或
订阅网关提供。

## 本地一键启动

要求：Docker Desktop，或 Docker Engine + Compose v2。

当前完整启动已在 macOS Docker Desktop 验证；脚本只依赖 Bash、Docker
Compose v2、`curl` 及 `openssl`（缺失时回退 `/dev/urandom`），面向 Linux
Docker Engine 保持兼容，但本次变更未在全新 Ubuntu 主机重新跑完整构建。

```bash
git clone https://github.com/xinzhuwang-wxz/StyleCapture-plus.git
cd StyleCapture-plus
./scripts/local.sh up
```

首次运行会创建权限为 `0600` 的 `.env.local`，自动生成本地内部 secrets，
构建并启动完整栈，然后等待 H5 与 API 真正 ready。镜像仓库或包仓库发生
瞬时网络错误时，脚本会复用已完成的构建缓存有限重试：

`.env.local` 默认沿用项目已在腾讯云部署验证过的 npm/PyPI 镜像；如所在网络
更适合官方源，可覆盖 `NPM_CONFIG_REGISTRY`、`UV_DEFAULT_INDEX` 和
`UV_LOCK_MIRROR_BASE`。

脚本不会删除或重建已有数据库卷。如果数据库由不兼容的开发分支迁移过，启动
会保留原始错误并退出，避免为了“成功”静默清空衣橱数据。
本地脚本默认使用独立 Compose 项目名 `stylecapture-local`，不会与同机名为
`stylecapture` 的生产栈共享容器或数据卷；需要并行安装时可设置
`STYLECAPTURE_COMPOSE_PROJECT_NAME`。

- H5：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8000/docs>
- LiteLLM（仅本机）：<http://127.0.0.1:4000>

如果仓库已有 `.env`，脚本会尊重它，不覆盖现有配置。也可显式指定：

```bash
STYLECAPTURE_ENV_FILE="$PWD/.env.local" ./scripts/local.sh up
```

常用命令：

```bash
./scripts/local.sh doctor   # 检查 Docker、Compose 和 Provider 配置
./scripts/local.sh status   # 查看服务健康状态
./scripts/local.sh logs     # 查看实时日志
./scripts/local.sh restart  # 保留数据并重新应用 Provider/模型配置
./scripts/local.sh down     # 停止容器，保留数据库、Redis 和上传卷
```

## 配置 AI API 或订阅网关

应用只调用 `reasoning`、`vision_understanding`、`outfit_analysis`、
`image_generation` 等稳定能力别名；Provider、模型名与凭据仅由 LiteLLM 知道。

### 推荐：豆包 / 方舟（完整体验）

编辑脚本生成的 `.env.local`：

```dotenv
ARK_API_KEY=你的方舟_API_Key
```

其余默认值已经对应项目验证过的模型：

```dotenv
STYLECAPTURE_AI_API_BASE=https://ark.cn-beijing.volces.com/api/v3
STYLECAPTURE_TEXT_MODEL=openai/doubao-seed-2-0-lite-260428
STYLECAPTURE_IMAGE_MODEL=openai/doubao-seedream-5-0-260128
```

### 其他 OpenAI-compatible API / 订阅服务

如果服务提供 OpenAI-compatible Base URL，可在 `.env.local` 中设置：

```dotenv
STYLECAPTURE_AI_API_KEY=你的订阅或_API_Key
STYLECAPTURE_AI_API_BASE=https://你的网关/v1
STYLECAPTURE_TEXT_MODEL=openai/你的多模态模型名
STYLECAPTURE_IMAGE_MODEL=openai/你的生图模型名
```

模型名包含 LiteLLM Provider 前缀，例如 `openai/...`、`openrouter/...` 或
`ollama/...`。文本模型必须支持图片理解，生图模型必须兼容 LiteLLM Images
接口。不同订阅不一定提供参考图生图或豆包 2048 维多模态 Embedding；缺失的
能力会返回真实的 partial/error，不会用 mock 冒充。需要完整的 Feed 拆解、
相似度、真人试穿和像素生成体验时，优先使用已验证的方舟配置。

修改配置后执行：

```bash
./scripts/local.sh restart
```

配置原理与可选重能力见 [技术决策](docs/architecture/TECHNICAL-DECISIONS.md) 和
[本地资源护栏](docs/engineering/LOCAL-RESOURCE-GUARDRAILS.md)。公网生产部署见
[deploy/README.md](deploy/README.md)。
