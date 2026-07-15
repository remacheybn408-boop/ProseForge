# 模型提供商

登录后进入 Settings，选择提供商、输入 API key 和可选 Base URL。保存后只显示掩码，原始密钥不会返回前端。

当前原生适配器包括 OpenAI Responses、Anthropic Messages 和 Google Gemini；本地端点必须显式加入 `PROSEFORGE_ALLOWED_LOCAL_PROVIDER_HOSTS`，避免服务端请求伪造。

生产环境必须设置随机的 `PROSEFORGE_MASTER_KEY` 和至少 32 字节的 `PROSEFORGE_JWT_SECRET`。
