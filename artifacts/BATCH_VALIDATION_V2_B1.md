> **⚠ 证据不可信（2026-07-18 撤销）**：本批次文档缺少逐条命令、退出码、镜像 digest 与 `down -v` 证据，按蓝图 `TEST_EXECUTION_POLICY.md` §五 不构成有效验证。真实状态以 `artifacts/VALIDATION_STATUS.md` 为准。

# V2 B1 Podman Batch

Tasks: V2-001/002/003. Workspace shell, immutable conversations and branches.

Evidence: V2 L2 Podman matrix and final Playwright suite; current final suite **10 passed**.
Command family: podman run --rm ... pytest -q and Playwright through the Podman browser image.
