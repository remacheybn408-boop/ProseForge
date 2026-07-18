# BATCH VALIDATION V2 B1（V2-001/002/003）

> 批次：B1（聊天外壳 + 消息模型 + 分支语义）。执行环境：Podman（compose.test.yaml 唯一编排）。本文件只记录真实执行过的命令与结果。

## 批次任务

| 任务 | 提交 | 内容 |
|---|---|---|
| V2-001 | `1c3135d` + `ce44894` | 工作台外壳：TanStack Router、三栏水墨布局、真实聊天组件、tokens 修复+守护测试、ordinary-user-smoke 解除 skip |
| V2-002 | `d72fb93` + `f13fdeb` | 消息模型真实化：generate_chat 全分支历史+system blocks+catalog 参数、ContextSnapshot 持久化、SSE live tail+心跳+started/completed/failed、v2 reasoning 422 |
| V2-003 | `04da8f2` + `49d5388` | 分支树与 fork 语义：regenerate attempt 递增、compare 消息级 diff、归档默认隐藏+UI toggle、候选切换器接真实数据 |
| B1 修复波 | `c702eb0`、`f408973` | vitest cleanup 基建、runtime-config.json、compose 测试 env、pytest 同名冲突、fixture 事件循环、WCAG 对比度 |

## Round 1（2026-07-19 00:06，工作树 = 49d5388）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `podman compose ... up -d --build --parallel 1 postgres redis` | 1 | docker-compose v5 provider 不支持 `--parallel` 标志；后续 `run` 自动拉起依赖，未影响测试 |
| `run --rm api-test pytest -q tests/api/test_conversation_branches.py tests/api/test_sse_reconnect.py tests/integration/conversations` | 0 | 17 passed, 14 skipped（skip 根因见下） |
| `run --rm api-test pytest -q tests/api` | 0 | 23 passed, 14 skipped |
| `run --rm api-test ruff check proseforge tests` | 0 | All checks passed |
| `run --rm web-test`（install+typecheck+vitest+build） | 1 | **16 failed / 44 passed**（4 个测试文件） |
| `down -v` | 0 | 已确认 |

Round 1 发现四类问题：vitest 无 RTL cleanup 基建（渲染跨用例累积 → 15 个"multiple elements"假阳性 + 1 个错误断言）；compose api-test 缺 `PROSEFORGE_TEST_*` env（14 个 PG API 测试全部 skip）；`tests/api` 与 `tests/integration/database` 同名文件冲突（CI 发现）；e2e 因 nginx 把 `/runtime-config.json` 回退为 index.html 导致登录卡死（CI 发现，3 个 spec 红）。

## Round 2（2026-07-19 01:15，工作树 = c702eb0）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `up -d --build postgres redis`（去掉 --parallel） | 0 | |
| api targeted / api full | 1 / 1 | PG 测试真正跑起来后暴露 fixture 事件循环 bug：裸 TestClient 每请求新开 anyio portal，asyncpg 连接跨 loop（"attached to a different loop"） |
| ruff | 0 | |
| web-test | 0 | **60 passed / 0 failed，typecheck 0，build 0** |
| `down -v` | 0 | 已确认 |

同轮 CI（c702eb0, run 29651590090）：matrix 三平台、pg-integration、lint、security、audit **绿**；docker-tests 红（同一 fixture 事件循环）、e2e 红（余 visual-a11y 对比度 `#9a9387` on `#fdfaf3` 2.92:1，两处）。

## Round 3（2026-07-19，工作树 = 68e3977，最终轮）

修复：`tests/api/conftest.py` TestClient 改上下文管理器（会话单 portal + 真实 lifespan）+ test profile 补 `data_dir`；`chat-shell.css` 小字 `--ink-light`→`--ink-mid`（2.92:1→~5.3:1，WCAG 2.2 AA；`--ink-light` 仅留 disabled/border）。追加两轮测试修复（`325f956`、`68e3977`）：heartbeat 测试改终止式写法（TestClient+BaseHTTPMiddleware 对永不结束的流不交付出首字节——测试基建限制，非产品 bug）；reconnect 断言改帧头计数；跨用户测试改共享 client + Bearer 头（裸 TestClient 每请求新 portal → asyncpg 跨 loop）；集成测试 PG 隔离（uuid 种子/限定快照与事件查询/唯一 crid）。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `up -d postgres redis` | 0 | |
| `run --rm api-test pytest -q tests/api/test_conversation_branches.py tests/api/test_sse_reconnect.py tests/integration/conversations` | 0 | **31 passed** |
| `run --rm api-test pytest -q tests/api` | 0 | **37 passed** |
| `run --rm api-test ruff check proseforge tests` | 0 | All checks passed |
| `run --rm web-test`（install+typecheck+vitest+build） | 0 | **60 passed（22 files），typecheck 0，build 0** |
| `down -v` | 0 | 已确认 |

## 偏差与决议记录

- `--parallel 1` 标志与 docker-compose v5 不兼容：批次脚本改为 `up -d --build postgres redis`。
- 蓝图 01 文件指定分支切换器 `--ink-light` 12px，与设计系统 §六（正文 ≥4.5:1，`--ink-light` 禁用于正文）冲突：按 a11y 硬门禁采用 `--ink-mid`，`--ink-light` 仅保留 disabled/border 装饰用途。
- vitest 新增 `vitest.setup.ts`（RTL cleanup）+ `setupFiles` 配置，属测试基建修复。
- `apps/web/public/runtime-config.json` 新增（`{"api_base_url":"/api","profile":"server"}`），修复 nginx SPA 回退吞掉运行时配置的产品 bug。

## 遗留（带入 B2）

- PG 真并发行为（regenerate 锁、approve 并发）无专项并发测试，靠 PG 层集成测试间接覆盖。
- `visual-a11y.spec.ts` 无自身 auth/setup，存在顺序依赖隐患（CI fullyParallel 下暴露时再修）。
