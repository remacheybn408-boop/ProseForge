# ProseForge Web v1 Docker 验收报告

日期：2026-07-16

所有项目测试和构建均在 Docker 容器内完成，宿主机没有运行 pytest、Node 或应用服务。

## 回归结果

| 检查 | 命令 | 结果 |
|---|---|---|
| Legacy 全量 | `docker run ... proseforge-web-v1-legacy-test:latest pytest -q` | **481 passed** |
| API/contract/unit | `docker compose ... run --rm api-test pytest -q tests/api tests/contract tests/unit` | **35 passed** |
| Migration/database | `docker compose ... run --rm migration-test pytest -q tests/migration tests/integration/database` | **12 passed** |
| Recovery/backup | `docker compose ... run --rm recovery-test pytest -q tests/recovery tests/integration/operations` | **4 passed** |
| Frontend | `docker compose ... run --rm web-test` | **2 Vitest passed; Vite build passed** |
| Static checks | Docker `ruff check` | passed |

## 真实容器流程

在运行中的 Compose 网络内验证了：

1. 首次 owner setup 和 cookie 登录
2. 创建/读取项目
3. 导入、确认大纲
4. 添加上下文条目
5. 创建章节和工作流
6. Celery worker 注册 `proseforge.chat.generate`
7. 未配置模型凭据时，聊天任务进入 `PARTIAL`，不会永久停留在 `PENDING`
8. Celery `inspect ping` 返回 `pong`
9. API live health 返回 200，所有 Compose 服务 healthy

## 修复的回归

- 修复数据库 revision 已到 head 但业务表缺失时 API 首次 setup 500；启动阶段现在执行迁移并安全补齐缺表。
- 修复应用任务只进入进程内存、worker 永远收不到的问题，改为 Redis/Celery 投递。
- 修复原生 Anthropic SSE 事件未统一为 `content.delta` 的问题。
- 修复 legacy importer 只归档不落库的问题。
