> **⚠ 证据不可信（2026-07-18 撤销）**：本批次文档缺少逐条命令、退出码、镜像 digest 与 `down -v` 证据，按蓝图 `TEST_EXECUTION_POLICY.md` §五 不构成有效验证。真实状态以 `artifacts/VALIDATION_STATUS.md` 为准。

# V1.5 B1 Podman Batch

Tasks: V15-000/001/002. Runtime profile, platform paths, bootstrap and lifecycle.

Command: podman run --rm ... pytest -q tests/runtime
Result: exit 0; **40 passed, 1 warning**.

All Python execution was inside the Podman test container. No host Python test was used.
