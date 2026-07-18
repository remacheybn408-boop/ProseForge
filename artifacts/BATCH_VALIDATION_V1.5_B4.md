> **⚠ 证据不可信（2026-07-18 撤销）**：本批次文档缺少逐条命令、退出码、镜像 digest 与 `down -v` 证据，按蓝图 `TEST_EXECUTION_POLICY.md` §五 不构成有效验证。真实状态以 `artifacts/VALIDATION_STATUS.md` 为准。

# V1.5 B4 Podman Batch

Tasks: V15-008/009. Packaging smoke and upgrade/rollback.

Command: podman run --rm ... pytest -q tests/packaging tests/operations tests/fault_injection
Result: exit 0; **5 passed**.

Linux source-runtime archive smoke passed in Podman. Native macOS signing and Windows installer execution remain not tested on this Windows host.
