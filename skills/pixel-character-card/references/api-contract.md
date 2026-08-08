# Product API 调用合同

脚本只使用 StyleCapture Product API，不直接调用 LiteLLM 或任何模型供应商。

## 顺序

1. `POST /v1/session`：未提供 `STYLECAPTURE_SESSION_COOKIE` 时建立私人会话。
2. `POST /v1/uploads/prepare`：提交 `file_name`、`content_type`、`byte_size`、`sha256`。
3. `PUT {upload_url}`：携带 `Content-Type` 与 `X-Upload-Token`，上传原始字节。
4. `POST /v1/pixel-trials`：正文为 `subject_object_key`，并携带新的 `Idempotency-Key`。
5. `GET /v1/pixel-trials/{trial_id}`：轮询到 `succeeded` 或 `failed`。
6. `GET /v1/pixel-trials/{trial_id}/image`：下载有背景的像素角色卡。
7. `GET /v1/pixel-trials/{trial_id}/sprite`：下载供像素世界使用的透明 PNG 小人。

## 边界

- 整体等待时间必须受 `--timeout-seconds` 限制。
- 只接受常见图片 MIME 类型，输入不得为空或超过 20 MB。
- HTTP 或业务错误只输出经过清理的状态码、错误码和消息，不输出 Cookie、上传令牌或响应头。
- Skill 不接收模型名、提示词、seed、guidance 或供应商密钥。这些属于服务端版本化能力合同。
