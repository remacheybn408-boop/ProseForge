> **⚠ 证据不可信（2026-07-18 撤销）**：本批次文档缺少逐条命令、退出码、镜像 digest 与 `down -v` 证据，按蓝图 `TEST_EXECUTION_POLICY.md` §五 不构成有效验证。真实状态以 `artifacts/VALIDATION_STATUS.md` 为准。

# V3 B1 Podman Batch

Tasks: V3-001/002/003. Agent ports, roles/policies and graph validation.

Command: podman run --rm ... pytest -q tests/agents tests/architecture tests/security
Result: exit 0; **15 passed**.
