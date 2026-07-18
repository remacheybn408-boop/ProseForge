> **⚠ 证据不可信（2026-07-18 撤销）**：本批次文档缺少逐条命令、退出码、镜像 digest 与 `down -v` 证据，按蓝图 `TEST_EXECUTION_POLICY.md` §五 不构成有效验证。真实状态以 `artifacts/VALIDATION_STATUS.md` 为准。

# V1.5 B3 Podman Batch

Tasks: V15-006/007. Same-origin Web, API, CLI/backup/doctor and recovery.

Command: podman run --rm ... pytest -q tests/api tests/cli tests/recovery
Result: exit 0; **28 passed, 2 warnings**.

Frontend unit/type/build evidence is included in the V1.5 L2 record and was run in Podman.
