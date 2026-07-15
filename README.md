# ProseForge Web v1

ProseForge 是一个 Docker-first 的长篇小说写作工作台：项目管理、章节版本、AI 对话、上下文、质量门禁、可恢复工作流和导出都在同一套 Web/API 架构中。

## 运行方式

只需要 Docker Desktop 和 Git。项目测试、构建和运行都通过 Docker 完成，宿主机不需要安装 Python、Node 或 pytest。

```bash
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
copy .env.example .env
docker compose up -d postgres redis
docker compose run --rm migration-test alembic upgrade head
docker compose up --build api worker scheduler web
```

打开 <http://localhost:3000> 使用 Web 界面；API 健康检查：

```text
GET http://localhost:8000/api/v1/health/live
GET http://localhost:8000/api/v1/health/ready
```

首次部署请修改 `.env` 中的 JWT secret、master key 和管理员密码。生产环境会拒绝默认占位值。

## Docker 测试

运行完整 legacy regression：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test
```

运行 API、迁移、恢复和前端测试：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm api-test
docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test
docker compose -f compose.yaml -f compose.test.yaml run --rm recovery-test
docker compose -f compose.yaml -f compose.test.yaml run --rm web-test
```

当前 Web v1 分支已在 Docker 中通过 476 个 Python 测试，以及前端 Vitest 和 Vite production build。

## 主要功能

- Projects / Writing Studio / Context / Workflow 工作区
- JWT 登录与项目 ownership 隔离
- PostgreSQL + Alembic 持久化，Redis/Celery worker 拓扑
- 会话分支、消息幂等、流式 chunk、SSE 重连
- Provider registry、OpenAI Responses 适配器、模型目录和加密凭据
- 内容寻址 BlobStore、安全上传检查、备份校验和恢复状态
- 大纲 intake、章节规划、规则质量门禁、rewrite limit 和整书暂停/恢复
- Legacy SQLite workspace 安全导入

## 兼容旧 CLI

旧 CLI 仅用于迁移期间的兼容操作：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test proseforge-legacy doctor
```

外部 Codex、Hermes、Claude Code plugin surfaces 已移除；Web/API 是主入口。

## 目录

```text
proseforge/                 Web v1 domain/application/API
apps/web/                   React + Vite frontend
docker/                     API、worker、web、test images
compose.yaml                production-like topology
compose.test.yaml           Docker-only test services
docs/plans/                 Codex execution plan
src/                        legacy compatibility core
```

详细 Docker 说明见 [docs/DOCKER_TESTING.md](docs/DOCKER_TESTING.md)，完整实施计划见 [docs/plans/PROSEFORGE_WEB_V1_CODEX_PLAN.md](docs/plans/PROSEFORGE_WEB_V1_CODEX_PLAN.md)。

## License

AGPL-3.0
