# V2 B4 Podman Batch

> 本文件取代 2026-07-18 被撤销的旧版（旧版缺逐条命令、退出码、镜像 digest 与 `down -v` 证据）。以下为 2026-07-20 在 ECS（36.213.79.118，Linux 原生 Docker）重跑的真实证据，全程日志见 `artifacts/v2-l2-run.log`。

Tasks: V2-008 / V2-009（workflow studio、导出、PWA、a11y/i18n），门禁 V2-010。

## 环境

| 项 | 值 |
|---|---|
| Git commit | `0687ed5a36a459f1bd637eb865074532e6f0de1d`（git archive 快照） |
| Docker | 29.6.2（server, Linux x86_64） |
| Compose | v5.3.1 |
| API image ID | `sha256:978070f676eb767fa4c94359b13a8ad43238cd5ca226bc0f9fef07cea01f0a71` |
| Worker image ID | `sha256:e19991dfe4061e978297d2cca0ddd0098c3545a08bfb8ef1ac96b099f51b9233` |
| Web image ID | `sha256:eb7140cbc6ab1e293ed41f3e07d408852484bce6bac10cacf451fbdd0126a0d2` |
| Playwright image ID | `sha256:be22982d683fe55ef44f66e042a08be636fa5db61de7479b7a7ddbefb2da6407`（v1.61.1-noble） |
| 起止时间 | 2026-07-20T14:57:36+08:00 → 15:06:58+08:00 |

## 逐条命令与结果

命令形式：`docker compose -f compose.yaml -f compose.test.yaml -f tmp-remote/compose.ecs.yaml <args>`（`compose.ecs.yaml` 仅追加 web 端口映射 21559/3000 与 npm 镜像源 env，不改变测试语义）。

| # | 步骤 | 退出码 | 结果 |
|---:|---|---:|---|
| 1 | `down -v`（前置清场） | 0 | — |
| 2 | `up -d --build --wait postgres redis provider-mock api worker web` | 0 | 全 healthy |
| 3 | `run --rm legacy-test` | 0 | 408 passed |
| 4 | `run --rm api-test` | 0 | 864 passed, 3 skipped |
| 5 | `run --rm contract-test` | 0 | 43 passed |
| 6 | `run --rm migration-test` | 0 | 24 passed |
| 7 | `run --rm recovery-test` | 0 | 5 passed |
| 8 | `run --rm web-test`（typecheck + 105 vitest + build） | 0 | 105 passed / 33 files |
| 9 | `run --rm e2e`（14 specs） | 0 | 12 passed, 2 skipped（v3 既定 skip），0 failed |
| 10 | `run --rm api-test ruff check proseforge tests` | 0 | All checks passed |
| 11 | `run --rm api-test python scripts/dump_openapi.py --output /app/artifacts/v2-openapi.json` | 0 | 111 paths，见 `artifacts/v2-openapi.json` |
| 12 | `down -v`（证据后拆栈） | 0 | 0 容器/镜像/卷残留 |

## 补充取证

professional-flow 证据附件（`testInfo.attach` 产物）由单独一次 spec 重跑收割（同代码同环境，JSON reporter 保留附件）：

- `artifacts/v2-export-evidence.json`：md/docx/epub 三格式 manifest + 下载 SHA-256（file_sha256 与下载值一致）
- `artifacts/v2-request-ids.json`：流程中捕获的 `x-correlation-id` 列表

## 服务器清理确认

批次结束后执行 `down -v --rmi local` + `docker image prune -f`：`docker ps -a` / `docker images` / `docker volume ls` 均无 proseforge 残留；仅保留 6 个通用基础镜像与 `/root/proseforge` 工作区（含 HF 缓存）。
